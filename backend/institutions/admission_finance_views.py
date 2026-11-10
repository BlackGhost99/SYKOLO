"""Configurable admission payment gate and evidence-backed government aid.

The director may verify an external government scholarship. No parent or
cashier can issue a scholarship; no award posts a cash payment or fee receipt.
"""
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import AcademicYear, AcademicLevel
from .admission_models import AdmissionApplication, AdmissionEvent
from .admission_finance import (
    AdmissionFinancePolicy, GovernmentScholarship, current_scholarship,
    finance_policy, payment_blocker, policy_scope,
)
from .models import School
from .parent_admission_models import ParentAdmissionRequest
from .parent_payment_models import AdmissionCashReceipt, ParentPaymentAttempt
from .services import has_permission
from .views import access, parse_body, log_event, refuse


def reject(reason, status=422):
    return JsonResponse({"error": reason}, status=status)


def parse_uuid(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def result(application):
    award = current_scholarship(application)
    policy = finance_policy(application.school, application.year_id, application.classroom.level_id)
    return {
        "policy": policy,
        "scholarship": ({
            "id": str(award.pk), "coverage": award.coverage,
            "official_reference": award.official_reference,
            "verified_at": award.verified_at.isoformat(),
            "revision": award.revision,
        } if award else None),
        "ready_for_enrollment": payment_blocker(application) is None,
        "blocker": payment_blocker(application),
    }


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def finance_rule(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    read = has_permission(request.user, school, "school.admissions.read") or has_permission(
        request.user, school, "school.settings.read"
    )
    edit = has_permission(request.user, school, "school.settings.write")
    if (request.method == "GET" and not read) or (request.method == "POST" and not edit):
        return refuse()
    if request.method == "GET":
        year_id = parse_uuid(request.GET.get("year"))
        level_id = parse_uuid(request.GET.get("level")) if request.GET.get("level") else None
        if year_id is None or (request.GET.get("level") and level_id is None):
            return reject("Année ou niveau invalide.")
        if not AcademicYear.objects.filter(school=school, pk=year_id).exists():
            return reject("Année étrangère à l'établissement.", 404)
        if level_id and not AcademicLevel.objects.filter(school=school, pk=level_id).exists():
            return reject("Niveau étranger à l'établissement.", 404)
        key = policy_scope(year_id, level_id)
        own = AdmissionFinancePolicy.objects.filter(school=school, scope_key=key).first()
        return JsonResponse({
            "year": str(year_id), "level": str(level_id) if level_id else None,
            "effective": finance_policy(school, year_id, level_id),
            "revision": own.revision if own else 0,
            "override": ({
                "require_payment": own.require_payment,
                "allow_government_scholarship": own.allow_government_scholarship
            } if own else None),
        })
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) != {
        "year", "level", "require_payment", "allow_government_scholarship", "revision"
    }:
        return reject("Configuration des frais incomplète.")
    year_id = parse_uuid(data["year"])
    level_id = parse_uuid(data["level"]) if data["level"] is not None else None
    if (not year_id or (data["level"] is not None and not level_id)
        or type(data["revision"]) is not int or data["revision"] < 0
        or type(data["require_payment"]) is not bool
        or type(data["allow_government_scholarship"]) is not bool):
        return reject("Année, niveau ou règle invalide.")
    if not AcademicYear.objects.filter(school=school, pk=year_id).exists():
        return reject("Année étrangère à l'établissement.")
    if level_id and not AcademicLevel.objects.filter(school=school, pk=level_id).exists():
        return reject("Niveau étranger à l'établissement.")
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        key = policy_scope(year_id, level_id)
        row = AdmissionFinancePolicy.objects.select_for_update().filter(school=school, scope_key=key).first()
        current_revision = row.revision if row else 0
        if data["revision"] != current_revision:
            return reject("La règle a été modifiée, rechargez-la.", 409)
        if row is None:
            row = AdmissionFinancePolicy(school=school, year_id=year_id, level_id=level_id, scope_key=key)
        row.require_payment = data["require_payment"]
        row.allow_government_scholarship = data["allow_government_scholarship"]
        row.revision = current_revision + 1
        try:
            row.full_clean()
            row.save()
        except ValidationError as exc:
            return reject(" ".join(exc.messages)[:500])
        log_event(school, request, "admission_finance_policy", str(row.pk),
                  {"require_payment": row.require_payment,
                   "allow_government_scholarship": row.allow_government_scholarship,
                   "year": str(year_id), "level": str(level_id) if level_id else None})
    return JsonResponse({"revision": row.revision, "effective": finance_policy(school, year_id, level_id)})


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def scholarship(request, school_id, application_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        if not has_permission(request.user, school, "school.admissions.read"):
            return refuse()
        application = AdmissionApplication.objects.select_related(
            "school", "classroom", "year"
        ).filter(school=school, pk=application_id).first()
        return JsonResponse(result(application)) if application else reject("Dossier inconnu.", 404)
    if not (has_permission(request.user, school, "school.admissions.decide")
            and has_permission(request.user, school, "school.finance.approve")):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) != {"action", "reference", "coverage", "revision"}:
        return reject("Décision de bourse incomplète.")
    if data["action"] not in ("approve", "revoke") or type(data["revision"]) is not int or data["revision"] < 0:
        return reject("Décision ou révision invalide.")
    reference = data["reference"]
    if not isinstance(reference, str) or len(reference.strip()) < 5 or len(reference) > 180:
        return reject("Référence justificative obligatoire (minimum cinq caractères).")
    if data["coverage"] not in ("all", "admission"):
        return reject("Choisissez une prise en charge totale ou des frais d'inscription seuls.")
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            application = AdmissionApplication.objects.select_for_update().select_related(
                "school", "classroom", "year"
            ).filter(school=school, pk=application_id).first()
            if application is None:
                return reject("Candidature introuvable.", 404)
            if application.status in ("enrolled", "rejected"):
                return reject("Une inscription définitive ou refusée ne peut pas changer de bourse.", 409)
            policy = finance_policy(school, application.year_id, application.classroom.level_id)
            if not policy["allow_government_scholarship"]:
                return reject("Les bourses gouvernementales sont désactivées pour ce niveau.", 409)
            award = GovernmentScholarship.objects.select_for_update().filter(
                school=school, application=application
            ).first()
            if (award.revision if award else 0) != data["revision"]:
                return reject("Cette bourse a déjà été modifiée.", 409)
            if data["action"] == "approve":
                link = ParentAdmissionRequest.objects.filter(application=application).first()
                if link:
                    from .singpay_models import SingPayIntent
                    active_singpay = SingPayIntent.objects.filter(
                        admission=link, school=school, mode="live",
                    ).exclude(state__in=("failed", "cancelled", "test_failed")).exists()
                    active_paycentral = ParentPaymentAttempt.objects.filter(
                        request=link, school=school, provider_mode="live",
                    ).exclude(state__in=("failed", "cancelled", "refunded")).exists()
                    if active_singpay or active_paycentral:
                        return reject("Un paiement en ligne est ouvert : rapprochez-le avant d'accorder une bourse.", 409)
                    paid_cash = AdmissionCashReceipt.objects.filter(
                        request=link, school=school, is_demo=False, void__isnull=True,
                    ).exists()
                    paid_online = ParentPaymentAttempt.objects.filter(
                        request=link, school=school, provider_mode="live", state="success",
                    ).exists()
                    if paid_cash or paid_online:
                        return reject("Des frais ont déjà été encaissés : traitez le remboursement avant la bourse.", 409)
                if award is None:
                    award = GovernmentScholarship(
                        school=school, application=application, verified_by=request.user
                    )
                award.active = True
                award.coverage = data["coverage"]
                award.official_reference = reference.strip()
                award.verified_by = request.user
                award.revision += (0 if award._state.adding else 1)
            else:
                if award is None or not award.active:
                    return reject("Aucune bourse active à retirer.", 409)
                award.active = False
                award.revision += 1
                award.official_reference = reference.strip()
            award.full_clean()
            award.save()
            code = "award_approved" if award.active else "award_revoked"
            AdmissionEvent.objects.create(
                school=school, application=application,
                previous_status=application.status, new_status=code,
                actor=request.user, reason="Décision de prise en charge documentée.",
            )
            log_event(school, request, code, str(award.pk),
                      {"coverage": award.coverage, "reference": award.official_reference})
    except ValidationError as exc:
        return reject(" ".join(exc.messages)[:500])
    except IntegrityError:
        return reject("Bourse déjà enregistrée, rechargez le dossier.", 409)
    return JsonResponse(result(application), status=201 if award.active else 200)
