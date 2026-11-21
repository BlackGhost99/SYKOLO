"""B3 school requests: own-only staff intake, separate independent review.

Never creates OperatingExpense, authorises a budget or moves money.
No teacher can read another request or call the financial budget endpoints.
"""
import re
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from accounts.views import authorized

from .academic_models import AcademicYear
from .models import SchoolMember
from .operating_models import (
    OperatingExpenseCategory, OperatingSupplier, OperatingClassificationOption,
)
from .operating_request_models import (
    OperatingSchoolRequest, OperatingSchoolRequestEvent,
    SCHOOL_REQUEST_STATES, SCHOOL_REQUEST_URGENCY,
)
from .operating_views import (
    body, fail, result, txt, day, money, uuidval, validation, open_year,
    CURRENCY,
)
from .operating_classification_service import pole_label
from .services import has_permission
from .views import access, refuse, log_event

QTY = re.compile(r"^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,2})?$")


def gate_request(request, school_id, *, review=False):
    school, err = access(request, school_id)
    if err is not None:
        return None, err
    if review:
        if not has_permission(request.user, school, "school.operating.approve"):
            return None, refuse()
    elif not any(has_permission(request.user, school, perm) for perm in (
        "school.operating.request", "school.operating.manage", "school.operating.approve",
    )):
        return None, refuse()
    return school, None


def can_review(user, school):
    return has_permission(user, school, "school.operating.approve")


def member_function(school, user):
    membership = SchoolMember.objects.select_related("role").filter(
        school=school, user=user, active=True, role__school=school,
    ).first()
    if not membership:
        raise ValueError("Compte du personnel non actif dans cet établissement.")
    return membership.role.label[:120]


def decimal_qty(value):
    if not isinstance(value, str) or not QTY.fullmatch(value):
        raise ValueError("Quantité décimale positive attendue.")
    num = Decimal(value)
    if num <= 0:
        raise ValueError("Quantité strictement positive attendue.")
    return num


def request_fields(school, data):
    # Never let requesters decide the budget or create a financial commitment.
    pole_label(school, "school")
    category = OperatingExpenseCategory.objects.filter(
        school=school, pk=uuidval(data["category"]), parent__isnull=True,
    ).first()
    if not category:
        raise LookupError("Catégorie scolaire introuvable.")
    if not category.active:
        raise ValueError("Catégorie archivée.")
    subcategory = None
    if data.get("subcategory"):
        subcategory = OperatingExpenseCategory.objects.filter(
            school=school, parent=category, pk=uuidval(data["subcategory"]),
        ).first()
        if not subcategory:
            raise LookupError("Sous-catégorie étrangère à cette famille.")
        if not subcategory.active:
            raise ValueError("Sous-catégorie archivée.")
    center = None
    if data.get("cost_center"):
        center = OperatingClassificationOption.objects.filter(
            school=school, kind="cost_center", pk=uuidval(data["cost_center"]),
        ).first()
        if not center:
            raise LookupError("Centre de coûts introuvable.")
        if not center.active or center.activity_pole not in ("", "school"):
            raise ValueError("Centre de coûts incompatible ou archivé.")
    supplier = None
    if data.get("supplier"):
        supplier = OperatingSupplier.objects.filter(
            school=school, pk=uuidval(data["supplier"]),
        ).first()
        if not supplier:
            raise LookupError("Fournisseur étranger à cet établissement.")
        if not supplier.active:
            raise ValueError("Fournisseur archivé.")
    year = AcademicYear.objects.filter(
        school=school, pk=uuidval(data["year"]),
    ).first()
    if not year:
        raise LookupError("Année scolaire inconnue.")
    if not open_year(year):
        raise ValueError("Année scolaire clôturée.")
    desired_on = day(data["desired_on"])
    if not year.start_date <= desired_on <= year.end_date:
        raise ValueError("Date souhaitée hors de l'année scolaire.")
    qty = decimal_qty(data["quantity"])
    estimated = money(data["estimated_amount"])
    unit = data.get("estimated_unit_price")
    if unit not in ("", None):
        unit = money(unit)
        if (unit * qty).quantize(Decimal("0.01")) != estimated:
            raise ValueError("Quantité × prix unitaire différent du montant estimé.")
    else:
        unit = None
    currency = data.get("currency", "XAF")
    if not isinstance(currency, str) or not CURRENCY.fullmatch(currency):
        raise ValueError("Code ISO de devise invalide.")
    urgency = data.get("urgency", "normal")
    if urgency not in dict(SCHOOL_REQUEST_URGENCY):
        raise ValueError("Niveau d'urgence invalide.")
    beneficiary = data.get("beneficiary_name", supplier.name if supplier else "")
    beneficiary = txt(beneficiary, 180, "Bénéficiaire ou fournisseur pressenti")
    return {
        "year": year, "service": txt(data["service"], 120, "Service"),
        "reason": txt(data["reason"], 600, "Motif"),
        "description": txt(data["description"], 200, "Objet de la demande"),
        "category": category, "subcategory": subcategory,
        "category_snapshot": category.name,
        "subcategory_snapshot": subcategory.name if subcategory else "",
        "cost_center": center,
        "cost_center_snapshot": center.name if center else "",
        "supplier": supplier, "beneficiary_name": beneficiary,
        "quantity": qty, "estimated_unit_price": unit,
        "estimated_amount": estimated, "currency": currency,
        "urgency": urgency, "desired_on": desired_on,
        "supporting_reference": txt(data.get("supporting_reference", ""), 240,
                                    "Référence justificative", optional=True),
    }


CREATE_ALLOWED = {
    "year", "service", "reason", "description", "category", "subcategory",
    "cost_center", "supplier", "beneficiary_name", "quantity",
    "estimated_unit_price", "estimated_amount", "currency", "urgency",
    "desired_on", "supporting_reference", "idempotency_key",
}
MANDATORY = {
    "year", "service", "reason", "description", "category", "quantity",
    "estimated_amount", "desired_on", "idempotency_key",
}


def request_data(row):
    return {
        "id": str(row.pk), "year": str(row.year_id),
        "requester": str(row.requester_id), "requester_name": row.requester.get_full_name() or row.requester.username,
        "requester_function": row.requester_function, "service": row.service,
        "reason": row.reason, "description": row.description,
        "category": str(row.category_id),
        "subcategory": str(row.subcategory_id) if row.subcategory_id else None,
        "category_label": row.category_snapshot, "subcategory_label": row.subcategory_snapshot,
        "cost_center": str(row.cost_center_id) if row.cost_center_id else None,
        "cost_center_label": row.cost_center_snapshot,
        "supplier": str(row.supplier_id) if row.supplier_id else None,
        "beneficiary_name": row.beneficiary_name,
        "quantity": format(row.quantity, ".2f"),
        "estimated_unit_price": format(row.estimated_unit_price, ".2f") if row.estimated_unit_price is not None else None,
        "estimated_amount": format(row.estimated_amount, ".2f"),
        "currency": row.currency, "urgency": row.urgency,
        "desired_on": row.desired_on.isoformat(),
        "supporting_reference": row.supporting_reference,
        "status": row.status, "revision": row.revision,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "created_at": row.created_at.isoformat(),
        "budget_committed": False, "money_transferred": False,
    }


def event_data(event):
    return {
        "action": event.action, "revision": event.revision,
        "actor": str(event.actor_id), "reason": event.reason,
        "happened_at": event.happened_at.isoformat(),
    }


def record(school, request, row, action, reason=""):
    item = OperatingSchoolRequestEvent(
        school=school, request=row, actor=request.user, action=action,
        reason=reason, revision=row.revision,
    )
    item.full_clean()
    item.save()
    log_event(school, request, "operating_school_request_" + action, row.pk)


def visible_requests(request, school):
    qs = OperatingSchoolRequest.objects.filter(school=school)
    if not can_review(request.user, school):
        qs = qs.filter(requester=request.user)
    return qs


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def school_requests(request, school_id):
    school, err = gate_request(request, school_id)
    if err is not None:
        return err
    if request.method == "GET":
        qs = visible_requests(request, school)
        if request.GET.get("mine") == "1":
            qs = qs.filter(requester=request.user)
        if request.GET.get("year"):
            try:
                year_id = uuidval(request.GET["year"])
            except ValueError as exc:
                return fail(str(exc))
            if not AcademicYear.objects.filter(school=school, pk=year_id).exists():
                return fail("Année scolaire introuvable.", 404)
            qs = qs.filter(year_id=year_id)
        status_filter = request.GET.get("status")
        if status_filter:
            if status_filter not in dict(SCHOOL_REQUEST_STATES):
                return fail("Statut invalide.")
            qs = qs.filter(status=status_filter)
        try:
            limit = int(request.GET.get("limit", "40"))
            offset = int(request.GET.get("offset", "0"))
        except (TypeError, ValueError):
            return fail("Pagination invalide.")
        if not (1 <= limit <= 100 and 0 <= offset <= 1000000):
            return fail("Pagination hors limites.")
        count = qs.count()
        rows = qs.select_related("requester").order_by("-created_at", "-id")[offset:offset+limit]
        return result({
            "requests": [request_data(row) for row in rows],
            "total": count, "offset": offset,
            "has_more": offset + len(rows) < count,
            "reviewer": can_review(request.user, school),
        })
    if not any(has_permission(request.user, school, perm) for perm in (
        "school.operating.request", "school.operating.manage"
    )):
        return refuse()
    data, err = body(request, CREATE_ALLOWED, MANDATORY)
    if err is not None:
        return err
    try:
        key = uuidval(data["idempotency_key"])
        existing = OperatingSchoolRequest.objects.filter(
            school=school, idempotency_key=key,
        ).first()
        if existing:
            if existing.requester_id == request.user.pk:
                return result({**request_data(existing), "idempotent": True})
            return fail("Clé d'idempotence déjà utilisée.", 409)
        fields = request_fields(school, data)
        function = member_function(school, request.user)
        with transaction.atomic():
            row = OperatingSchoolRequest(
                school=school, requester=request.user, requester_function=function,
                idempotency_key=key, **fields
            )
            row.full_clean()
            row.save()
            log_event(school, request, "operating_school_request_prepared", row.pk)
    except LookupError as exc:
        return fail(str(exc), 404)
    except (ValueError, TypeError) as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    except IntegrityError:
        return fail("Demande déjà reçue, actualisez la liste.", 409)
    return result(request_data(row), 201)


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def school_request_detail(request, school_id, request_id):
    school, err = gate_request(request, school_id)
    if err is not None:
        return err
    if request.method == "GET":
        row = visible_requests(request, school).select_related("requester").filter(
            pk=request_id
        ).first()
        if not row:
            return fail("Demande introuvable.", 404)
        return result({
            "request": request_data(row),
            "history": [event_data(e) for e in row.events.order_by("happened_at", "pk")],
        })
    data, err = body(request, CREATE_ALLOWED - {"idempotency_key"} | {"revision"}, {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int or len(data) == 1:
        return fail("Révision et modification obligatoires.")
    try:
        with transaction.atomic():
            row = OperatingSchoolRequest.objects.select_for_update(of=("self",)).select_related(
                "year", "category", "subcategory", "supplier", "cost_center", "requester",
            ).filter(school=school, pk=request_id, requester=request.user).first()
            if not row:
                return fail("Demande personnelle introuvable.", 404)
            if row.revision != data["revision"]:
                return fail("Demande modifiée par un autre utilisateur.", 409)
            if row.status not in ("draft", "rejected") or not open_year(row.year):
                return fail("Cette demande ne peut plus être modifiée.", 409)
            merged = {
                "year": str(row.year_id), "service": row.service, "reason": row.reason,
                "description": row.description, "category": str(row.category_id),
                "subcategory": str(row.subcategory_id) if row.subcategory_id else None,
                "cost_center": str(row.cost_center_id) if row.cost_center_id else None,
                "supplier": str(row.supplier_id) if row.supplier_id else None,
                "beneficiary_name": row.beneficiary_name,
                "quantity": format(row.quantity, ".2f"),
                "estimated_unit_price": format(row.estimated_unit_price, ".2f")
                    if row.estimated_unit_price is not None else None,
                "estimated_amount": format(row.estimated_amount, ".2f"),
                "currency": row.currency, "urgency": row.urgency,
                "desired_on": row.desired_on.isoformat(),
                "supporting_reference": row.supporting_reference,
            }
            merged.update({k:v for k,v in data.items() if k!="revision"})
            # Year cannot be changed via an edit: closing/reassignment is handled
            # by a new request, never by moving a submitted historical request.
            if str(row.year_id) != str(merged["year"]):
                return fail("Année de la demande immuable.", 409)
            fields = request_fields(school, merged)
            for name, value in fields.items():
                setattr(row, name, value)
            rejected = row.status == "rejected"
            if rejected:
                row.status = "draft"
                row.reviewed_by = None
                row.reviewed_at = None
                row.decided_by = None
                row.decided_at = None
            row.revision += 1
            row.full_clean()
            row.save()
            if rejected:
                record(school, request, row, "revised")
            else:
                log_event(school, request, "operating_school_request_updated", row.pk)
    except LookupError as exc:
        return fail(str(exc), 404)
    except (ValueError, TypeError) as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    return result(request_data(row))


@never_cache
@require_POST
@authorized
def school_request_action(request, school_id, request_id, action):
    if action not in {"submit", "review", "cancel"}:
        return fail("Action inconnue.", 404)
    school, err = gate_request(request, school_id, review=(action == "review"))
    if err is not None:
        return err
    allowed = {"revision", "decision", "reason"} if action == "review" else {"revision"}
    data, err = body(request, allowed, {"revision", "decision"} if action=="review" else {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int:
        return fail("Révision obligatoire.")
    try:
        with transaction.atomic():
            qs = OperatingSchoolRequest.objects.select_for_update(of=("self",)).select_related(
                "requester", "year", "category", "subcategory", "cost_center", "supplier",
            ).filter(school=school, pk=request_id)
            if action != "review":
                qs = qs.filter(requester=request.user)
            row = qs.first()
            if not row:
                return fail("Demande introuvable.", 404)
            if row.revision != data["revision"]:
                return fail("La demande a changé depuis votre dernière consultation.", 409)
            if action == "submit":
                if row.status != "draft" or not open_year(row.year):
                    return fail("Seul un brouillon d'un exercice ouvert peut être soumis.", 409)
                if not row.category.active or (row.subcategory_id and not row.subcategory.active):
                    return fail("Catégorie archivée : corrigez le brouillon.", 409)
                if row.cost_center_id and not row.cost_center.active:
                    return fail("Centre de coûts archivé.", 409)
                row.status = "submitted"
                row.submitted_at = timezone.now()
                event = "submitted"
                reason = ""
            elif action == "cancel":
                if row.status not in ("draft", "rejected", "submitted", "in_review"):
                    return fail("Demande déjà traitée ou annulée.", 409)
                row.status = "cancelled"
                event = "cancelled"
                reason = ""
            else:
                if row.requester_id == request.user.pk:
                    return fail("Une demande ne peut être examinée par son auteur.", 403)
                if not open_year(row.year):
                    return fail("Exercice clôturé.", 409)
                decision = data["decision"]
                reason = data.get("reason", "")
                if not isinstance(reason, str) or len(reason.strip()) > 500:
                    return fail("Motif invalide.")
                reason = reason.strip()
                if decision == "in_review" and row.status == "submitted":
                    row.status = "in_review"
                    row.reviewed_by = request.user
                    row.reviewed_at = timezone.now()
                    event = "in_review"
                elif decision == "approved" and row.status == "in_review":
                    row.status = "approved"
                    row.decided_by = request.user
                    row.decided_at = timezone.now()
                    event = "approved"
                elif decision == "rejected" and row.status in ("submitted", "in_review"):
                    if len(reason) < 10:
                        return fail("Motif de refus de 10 caractères minimum obligatoire.")
                    row.status = "rejected"
                    row.decided_by = request.user
                    row.decided_at = timezone.now()
                    event = "rejected"
                else:
                    return fail("Transition d'autorisation invalide.", 409)
            row.revision += 1
            row.full_clean()
            row.save()
            record(school, request, row, event, reason)
    except ValidationError as exc:
        return validation(exc)
    return result(request_data(row))
