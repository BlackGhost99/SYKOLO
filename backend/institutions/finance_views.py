"""Module 11: recorded school fees and manual receipts only; no payment gateway."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from html import escape
from uuid import UUID

from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from accounts.views import authorized

from .academic_models import AcademicYear, AcademicClass
from .finance_models import FeeSchedule, FeeCharge, FeePayment, FeePaymentVoid
from .finance_cash_policy import cash_closed_for_recorder
from .models import School
from .student_models import Enrollment
from .services import has_permission
from .views import access, refuse, parse_body, log_event


MAX_MONEY = Decimal("9999999999.99")
MONEY_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?\Z")
CODE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
CURRENCY_PATTERN = re.compile(r"[A-Z]{3}\Z")


def gate(request, school_id, permission):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, permission):
        return None, refuse()
    return school, None


def money(value):
    if type(value) not in (str, int):
        raise ValueError("Montant décimal requis, sans nombre flottant.")
    text = str(value)
    if not MONEY_PATTERN.fullmatch(text):
        raise ValueError("Montant invalide : deux décimales maximum.")
    try:
        result = Decimal(text)
    except InvalidOperation:
        raise ValueError("Montant invalide.") from None
    if result <= 0 or result > MAX_MONEY:
        raise ValueError("Le montant doit être positif et dans les limites autorisées.")
    return result.quantize(Decimal("0.01"))


def iso_day(value, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Date ISO requise.")
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
    except ValueError:
        raise ValueError("Date ISO invalide.") from None
    return parsed


def uid(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except (TypeError, ValueError):
        return None


def label(value, maximum=160):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise ValueError("Libellé invalide.")
    return value.strip()


def model_error(exc):
    if hasattr(exc, "message_dict"):
        return JsonResponse({"error": " ".join(x for messages in exc.message_dict.values() for x in messages)[:500]}, status=422)
    return JsonResponse({"error": " ".join(exc.messages)[:500]}, status=422)


def schedule_data(row):
    return {
        "id": str(row.pk), "year": str(row.year_id),
        "classroom": str(row.classroom_id) if row.classroom_id else None,
        "code": row.code, "label": row.label, "amount": str(row.amount),
        "currency": row.currency, "due_date": row.due_date.isoformat() if row.due_date else None,
        "active": row.active, "revision": row.revision,
    }


def cleared_total(charge):
    value = FeePayment.objects.filter(charge=charge, void__isnull=True).aggregate(
        total=Sum("amount")
    )["total"]
    return value or Decimal("0.00")


def charge_data(row):
    paid = cleared_total(row)
    return {
        "id": str(row.pk), "enrollment": str(row.enrollment_id),
        "schedule": str(row.schedule_id),
        "label": row.label, "amount": str(row.amount),
        "scholarship_discount": str(row.scholarship_discount),
        "net_amount": str((row.amount - row.scholarship_discount).quantize(Decimal("0.01"))),
        "currency": row.currency,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "paid": str(paid.quantize(Decimal("0.01"))),
        "balance": str((row.amount - row.scholarship_discount - paid).quantize(Decimal("0.01"))),
    }


def payment_data(row):
    return {
        "id": str(row.pk), "charge": str(row.charge_id),
        "amount": str(row.amount), "currency": row.currency,
        "method": row.method, "reference": row.reference,
        "paid_on": row.paid_on.isoformat(), "recorded_at": row.created_at.isoformat(),
        "voided": FeePaymentVoid.objects.filter(payment=row).exists(),
    }


def schedule_fields(data, updating=False):
    allowed = {"code", "year", "classroom", "label", "amount", "currency", "due_date", "active"}
    if updating:
        allowed -= {"code", "year", "classroom"}
    if set(data) - allowed - ({"revision"} if updating else set()):
        raise ValueError("Champs tarifaires non autorisés.")
    required = {"code", "year", "label", "amount", "currency"} if not updating else {"revision"}
    if not required <= set(data):
        raise ValueError("Champs obligatoires manquants.")
    if updating and (type(data["revision"]) is not int or data["revision"] < 1 or len(data) == 1):
        raise ValueError("Révision invalide ou aucune modification.")
    result = {}
    for key, value in data.items():
        if key == "revision":
            continue
        if key == "code":
            if not isinstance(value, str) or not CODE_PATTERN.fullmatch(value):
                raise ValueError("Code de frais invalide.")
        if key in ("year", "classroom"):
            if key == "classroom" and value is None:
                result["classroom_id"] = None
                continue
            value = uid(value)
            if value is None:
                raise ValueError("Identifiant scolaire invalide.")
            key += "_id"
        elif key == "label":
            value = label(value)
        elif key == "amount":
            value = money(value)
        elif key == "currency":
            if not isinstance(value, str) or not CURRENCY_PATTERN.fullmatch(value):
                raise ValueError("Devise ISO à trois lettres requise.")
        elif key == "due_date":
            value = iso_day(value, optional=True)
        elif key == "active":
            if type(value) is not bool:
                raise ValueError("Statut invalide.")
        result[key] = value
    return result


@require_http_methods(["GET", "POST"])
@authorized
def schedules(request, school_id):
    school, error = gate(request, school_id, "school.finance.read" if request.method == "GET" else "school.finance.manage")
    if error is not None:
        return error
    if request.method == "GET":
        rows = FeeSchedule.objects.filter(school=school).order_by("year__start_date", "label")[:500]
        result = {"schedules": [schedule_data(row) for row in rows]}
        if request.GET.get("choices") == "1":
            if not has_permission(request.user, school, "school.finance.manage"):
                return refuse()
            years = AcademicYear.objects.filter(school=school, active=True).order_by("-start_date")
            classes = AcademicClass.objects.filter(school=school, year__active=True, active=True).order_by("name", "pk")
            result["years"] = list(years.values("id", "name", "active"))
            result["classes"] = [
                {"id": room.pk, "name": room.name, "year": room.year_id, "active": room.active}
                for room in classes
            ]
        return JsonResponse(result)
    data, error = parse_body(request)
    if error is not None:
        return error
    try:
        values = schedule_fields(data)
        if not AcademicYear.objects.filter(school=school, pk=values["year_id"], active=True).exists():
            raise ValueError("Année scolaire introuvable.")
        classroom_id = values.get("classroom_id")
        if classroom_id and not AcademicClass.objects.filter(
            school=school, year_id=values["year_id"], pk=classroom_id, active=True
        ).exists():
            raise ValueError("Classe introuvable dans cette année.")
        values["scope_key"] = str(classroom_id) if classroom_id else ""
        with transaction.atomic():
            row = FeeSchedule(school=school, **values)
            row.full_clean()
            row.save()
            log_event(school, request, "fee_schedule_created", row.pk)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Frais déjà configuré pour cette portée."}, status=409)
    return JsonResponse(schedule_data(row), status=201)


@require_http_methods(["GET", "PATCH"])
@authorized
def schedule_detail(request, school_id, schedule_id):
    school, error = gate(request, school_id, "school.finance.read" if request.method == "GET" else "school.finance.manage")
    if error is not None:
        return error
    if request.method == "GET":
        row = FeeSchedule.objects.filter(school=school, pk=schedule_id).first()
        return JsonResponse(schedule_data(row)) if row else JsonResponse({"error": "Frais introuvable."}, status=404)
    data, error = parse_body(request)
    if error is not None:
        return error
    try:
        changes = schedule_fields(data, updating=True)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            row = FeeSchedule.objects.select_for_update().filter(school=school, pk=schedule_id).first()
            if row is None:
                return JsonResponse({"error": "Frais introuvable."}, status=404)
            if row.revision != data["revision"]:
                return JsonResponse({"error": "Conflit de version.", "revision": row.revision}, status=409)
            for key, value in changes.items():
                setattr(row, key, value)
            row.full_clean()
            row.revision += 1
            row.save()
            log_event(school, request, "fee_schedule_updated", row.pk)
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Tarif déjà existant."}, status=409)
    return JsonResponse(schedule_data(row))


@require_http_methods(["GET", "POST"])
@authorized
def charges(request, school_id):
    school, error = gate(request, school_id, "school.finance.read" if request.method == "GET" else "school.finance.manage")
    if error is not None:
        return error
    if request.method == "GET":
        query = FeeCharge.objects.select_related("schedule").filter(school=school)
        if "enrollment" in request.GET:
            key = uid(request.GET.get("enrollment"))
            if key is None:
                return JsonResponse({"error": "Inscription invalide."}, status=422)
            query = query.filter(enrollment_id=key)
        return JsonResponse({"charges": [charge_data(row) for row in query.order_by("created_at")[:500]]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"enrollment", "schedule"}:
        return JsonResponse({"error": "Champs de facturation invalides."}, status=422)
    try:
        with transaction.atomic():
            enrollment = Enrollment.objects.select_for_update().filter(
                school=school, pk=uid(data["enrollment"]), active=True, student__active=True
            ).first()
            if enrollment is None:
                return JsonResponse({"error": "Inscription introuvable."}, status=404)
            schedule = FeeSchedule.objects.filter(school=school, pk=uid(data["schedule"]), active=True).first()
            if schedule is None:
                return JsonResponse({"error": "Tarif introuvable."}, status=404)
            from .admission_scholarship_amounts import tuition_discount
            covered = tuition_discount(enrollment, schedule)
            if covered >= schedule.amount:
                return JsonResponse({"error": "Ce frais est intégralement pris en charge par la bourse."}, status=409)
            row = FeeCharge(
                school=school, enrollment=enrollment, schedule=schedule,
                label=schedule.label, amount=schedule.amount, scholarship_discount=covered, currency=schedule.currency,
                due_date=schedule.due_date, created_by=request.user,
            )
            row.full_clean()
            row.save()
            log_event(school, request, "fee_charge_created", row.pk)
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Frais déjà affecté à l'inscription."}, status=409)
    return JsonResponse(charge_data(row), status=201)


@require_GET
@authorized
def charge_detail(request, school_id, charge_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    row = FeeCharge.objects.select_related("schedule").filter(school=school, pk=charge_id).first()
    return JsonResponse(charge_data(row)) if row else JsonResponse({"error": "Frais affecté introuvable."}, status=404)


@require_http_methods(["GET", "POST"])
@authorized
def payments(request, school_id):
    school, error = gate(request, school_id, "school.finance.read" if request.method == "GET" else "school.finance.receive")
    if error is not None:
        return error
    if request.method == "GET":
        charge_id = uid(request.GET.get("charge"))
        if charge_id is None:
            return JsonResponse({"error": "Identifiant du frais requis."}, status=422)
        if not FeeCharge.objects.filter(school=school, pk=charge_id).exists():
            return JsonResponse({"error": "Frais affecté introuvable."}, status=404)
        rows = FeePayment.objects.filter(school=school, charge_id=charge_id).order_by("created_at", "pk")[:500]
        return JsonResponse({"payments": [payment_data(row) for row in rows]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"charge", "amount", "method", "reference", "paid_on", "idempotency_key"}:
        return JsonResponse({"error": "Champs d'encaissement invalides."}, status=422)
    charge_id = uid(data["charge"])
    idem = uid(data["idempotency_key"])
    method = data["method"]
    reference = data["reference"]
    if method == "singpay":
        return JsonResponse({"error": "SingPay est réservé aux confirmations serveur du prestataire."}, status=422)
    if charge_id is None or idem is None or not isinstance(method, str) or not CODE_PATTERN.fullmatch(method):
        return JsonResponse({"error": "Frais, moyen ou identifiant d'opération invalide."}, status=422)
    if not isinstance(reference, str) or len(reference) > 100:
        return JsonResponse({"error": "Référence invalide."}, status=422)
    try:
        amount = money(data["amount"])
        paid_on = iso_day(data["paid_on"])
        if paid_on > timezone.localdate():
            raise ValueError("Un encaissement futur ne peut pas être déclaré comme reçu.")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            if method == "especes":
                # Lock order matches the cash-closing endpoint, avoiding a race
                # between a cashier's last payment and the end-of-day snapshot.
                School.objects.select_for_update().get(pk=school.pk)
            charge = FeeCharge.objects.select_for_update().filter(school=school, pk=charge_id).first()
            if charge is None:
                return JsonResponse({"error": "Frais affecté introuvable."}, status=404)
            previous = FeePayment.objects.filter(school=school, idempotency_key=idem).first()
            if previous:
                same = (previous.charge_id == charge.pk and previous.amount == amount
                    and previous.method == method and previous.reference == reference.strip()
                    and previous.paid_on == paid_on)
                if same:
                    return JsonResponse(payment_data(previous), status=200)
                return JsonResponse({"error": "Clé d'opération réutilisée avec des données différentes."}, status=409)
            if method == "especes" and cash_closed_for_recorder(
                school=school, day=paid_on, currency=charge.currency, user=request.user,
            ):
                return JsonResponse({"error": "Caisse du jour déjà déclarée par ce caissier."}, status=409)
            if cleared_total(charge) + amount > charge.amount - charge.scholarship_discount:
                return JsonResponse({"error": "Montant supérieur au solde restant dû."}, status=422)
            row = FeePayment(
                school=school, charge=charge, idempotency_key=idem,
                amount=amount, currency=charge.currency, method=method,
                reference=reference.strip(), paid_on=paid_on, recorded_by=request.user,
            )
            row.full_clean()
            row.save()
            log_event(school, request, "fee_payment_recorded", row.pk)
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Encaissement concurrent ou en double ; vérifiez le relevé."}, status=409)
    return JsonResponse(payment_data(row), status=201)


@require_POST
@authorized
def void_payment(request, school_id, payment_id):
    school, error = gate(request, school_id, "school.finance.reverse")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"reason"} or not isinstance(data["reason"], str) or not 10 <= len(data["reason"].strip()) <= 1000:
        return JsonResponse({"error": "Motif d'annulation obligatoire (10 à 1000 caractères)."}, status=422)
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        row = FeePayment.objects.select_related("charge").filter(school=school, pk=payment_id).first()
        if row is None:
            return JsonResponse({"error": "Paiement introuvable."}, status=404)
        if row.method == "singpay":
            return JsonResponse({"error": "Paiement prestataire : remboursement et rapprochement requis, annulation manuelle interdite."}, status=409)
        if row.recorded_by_id == request.user.pk:
            return JsonResponse({"error": "Un autre agent doit autoriser cette annulation."}, status=403)
        if row.method == "especes" and cash_closed_for_recorder(school=school, day=row.paid_on, currency=row.currency, user=row.recorded_by):
            return JsonResponse({"error": "Caisse déclarée : annulation bloquée pour préserver le contrôle."}, status=409)
        FeeCharge.objects.select_for_update().get(pk=row.charge_id, school=school)
        if FeePaymentVoid.objects.filter(school=school, payment=row).exists():
            return JsonResponse({"error": "Paiement déjà annulé."}, status=409)
        void = FeePaymentVoid(school=school, payment=row, reason=data["reason"].strip(), approved_by=request.user)
        void.full_clean()
        void.save()
        log_event(school, request, "fee_payment_voided", row.pk)
    return JsonResponse({"id": str(void.pk), "payment": str(row.pk), "voided": True}, status=201)


@require_GET
@authorized
def statement(request, school_id, enrollment_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    enrollment = Enrollment.objects.filter(school=school, pk=enrollment_id).first()
    if enrollment is None:
        return JsonResponse({"error": "Inscription introuvable."}, status=404)
    charges_list = list(FeeCharge.objects.select_related("schedule").filter(
        school=school, enrollment=enrollment
    ).order_by("created_at"))
    totals = {}
    result = []
    for charge in charges_list:
        item = charge_data(charge)
        currency = charge.currency
        total = totals.setdefault(currency, {
            "billed": Decimal("0.00"), "paid": Decimal("0.00"), "balance": Decimal("0.00"),
        })
        # The statement reports the post-scholarship amount actually owed,
        # rather than counting the grant as an unpaid school fee.
        total["billed"] += Decimal(item["net_amount"])
        total["paid"] += Decimal(item["paid"])
        total["balance"] += Decimal(item["balance"])
        result.append(item)
    return JsonResponse({
        "enrollment": str(enrollment.pk), "student": str(enrollment.student_id),
        "charges": result,
        "totals": {currency: {key: str(value) for key, value in values.items()}
                   for currency, values in totals.items()},
    })


@require_GET
@authorized
def receipt(request, school_id, payment_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    payment = FeePayment.objects.select_related(
        "charge__schedule", "charge__enrollment__student"
    ).filter(school=school, pk=payment_id).first()
    if payment is None:
        return JsonResponse({"error": "Reçu introuvable."}, status=404)
    void = FeePaymentVoid.objects.filter(payment=payment, school=school).first()
    from .finance_quality_views import explicit_demo
    simulated = (payment.method == "simulation"
                 or explicit_demo(payment.charge.label)
                 or explicit_demo(payment.charge.schedule.label))
    unverified_legacy = payment.method == "cash" and not simulated
    receipt_class = ("simulation" if simulated else
                     "legacy_unverified" if unverified_legacy else "manual_record")
    heading = (
        "YEM — SIMULATION FINANCIÈRE — AUCUN ARGENT REÇU"
        if simulated else
        "YEM — ÉCRITURE HISTORIQUE NON RAPPROCHÉE — PAS UN REÇU D'ESPÈCES"
        if unverified_legacy else
        "YEM — REÇU D'ENCAISSEMENT ENREGISTRÉ"
    )
    student = payment.charge.enrollment.student
    lines = [
        heading,
        "Référence interne : " + str(payment.pk),
        "Établissement : " + school.name,
        "Élève : " + student.first_name + " " + student.last_name,
        "Frais : " + payment.charge.label,
        "Montant enregistré : " + str(payment.amount) + " " + payment.currency,
        "Date déclarée : " + payment.paid_on.isoformat(),
        "Méthode déclarée : " + payment.method,
        "Référence : " + (payment.reference or "Non renseignée"),
        "Statut : ANNULÉ — ne vaut plus preuve d'encaissement." if void else
        "Statut : SIMULATION — aucune recette réelle." if simulated else
        "Statut : À RAPPROCHER — déclaration historique non vérifiée." if unverified_legacy else
        "Statut : Enregistré par l'établissement.",
        "Document interne : aucune confirmation automatique d'un établissement bancaire ou opérateur mobile.",
    ]
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(line), styles["Normal"]) for line in lines]
    story.insert(1, Spacer(1, 8*mm))
    document.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="yem-recu-{payment.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    response["X-YEM-Receipt-Class"] = receipt_class
    return response
