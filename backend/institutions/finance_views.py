"""Module 11: recorded school fees and manual receipts only; no payment gateway."""
import re
from calendar import monthrange
from datetime import date
from unicodedata import normalize
from decimal import Decimal, InvalidOperation
from io import BytesIO
from html import escape
from uuid import UUID

from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from accounts.views import authorized

from .finance_document_pdf import previewable_pdf

from .academic_models import AcademicYear, AcademicClass
from .finance_models import FeeSchedule, FeeCharge, FeePayment, FeePaymentVoid
from .finance_cash_policy import CASH_METHODS, cash_closed_for_recorder
from .finance_evidence import classify_payment
from .models import School
from .student_models import Enrollment
from .services import has_permission, can_configure_tariffs, platform_tariff_intervention
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
    evidence = classify_payment(row.method, row.charge.label)
    return {
        "id": str(row.pk), "charge": str(row.charge_id),
        "evidence_class": evidence,
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


def tariff_gate(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if request.method == "GET":
        allowed = has_permission(request.user, school, "school.finance.read") or platform_tariff_intervention(request, school)
    else:
        allowed = can_configure_tariffs(request, school)
    return (school, None) if allowed else (None, refuse())


@require_http_methods(["GET", "POST"])
@authorized
def schedules(request, school_id):
    school, error = tariff_gate(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        rows = FeeSchedule.objects.filter(school=school).order_by("year__start_date", "label", "pk")
        # The settings catalog must include every generated tariff; a monthly
        # setup can legitimately contain more than 500 class/month entries.
        result = {"schedules": [schedule_data(row) for row in rows]}
        if request.GET.get("choices") == "1":
            if not can_configure_tariffs(request, school):
                return refuse()
            years = AcademicYear.objects.filter(school=school, active=True).order_by("-start_date")
            classes = AcademicClass.objects.filter(school=school, year__active=True, active=True).select_related("level__cycle").order_by("name", "pk")
            result["years"] = list(years.values("id", "name", "active"))
            result["classes"] = [
                {"id": room.pk, "name": room.name, "year": room.year_id, "active": room.active,
                 "cycle": room.level.cycle_id, "cycle_name": room.level.cycle.name,
                 "level": room.level_id, "level_name": room.level.name}
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


def monthly_dates(first, last, day):
    if (not isinstance(first, str) or not isinstance(last, str)
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", first)
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", last)
            or type(day) is not int or not 1 <= day <= 31):
        raise ValueError("Mois ou jour d’échéance invalide.")
    start = date.fromisoformat(first + "-01")
    end = date.fromisoformat(last + "-01")
    count = (end.year - start.year) * 12 + end.month - start.month + 1
    if not 1 <= count <= 24:
        raise ValueError("Sélectionnez une période de 1 à 24 mois.")
    result = []
    for offset in range(count):
        y, m = divmod(start.year * 12 + start.month - 1 + offset, 12)
        result.append(date(y, m + 1, min(day, monthrange(y, m + 1)[1])))
    return result


def tuition_like(row):
    text = normalize("NFKD", row.code + " " + row.label).encode("ascii", "ignore").decode().lower()
    return any(word in text for word in ("scolarite", "mensualite", "tuition"))


@require_POST
@authorized
def generate_monthly_schedules(request, school_id):
    """Generate price schedules only; never create a student's charges or payment."""
    school, error = tariff_gate(request, school_id)
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    try:
        if set(data) != {"year", "classrooms", "amount", "first_month", "last_month", "due_day"}:
            raise ValueError("Paramètres de génération incomplets.")
        ids = data["classrooms"]
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
            raise ValueError("Sélectionnez entre 1 et 100 classes.")
        selected = [uid(value) for value in ids]
        if None in selected or len(set(selected)) != len(selected):
            raise ValueError("Sélection de classes invalide ou répétée.")
        year_id = uid(data["year"])
        if year_id is None:
            raise ValueError("Année invalide.")
        amount = money(data["amount"])
        if amount != amount.to_integral_value():
            raise ValueError("Saisissez un montant en francs CFA entiers.")
        dates = monthly_dates(data["first_month"], data["last_month"], data["due_day"])
        if len(selected) * len(dates) > 1200:
            raise ValueError("Limitez une génération à 1 200 tarifs.")
        with transaction.atomic():
            # The school lock serializes concurrent bulk generation requests.
            School.objects.select_for_update().get(pk=school.pk)
            year = AcademicYear.objects.select_for_update().filter(
                pk=year_id, school=school, active=True,
            ).exclude(status=AcademicYear.STATUS_CLOSED).first()
            if year is None:
                raise ValueError("Année scolaire inactive, clôturée ou étrangère.")
            if any(day < year.start_date or day > year.end_date for day in dates):
                raise ValueError("Toutes les échéances doivent être comprises dans l’année scolaire.")
            rooms = AcademicClass.objects.filter(
                school=school, year=year, pk__in=selected, active=True,
                level__active=True, level__cycle__active=True,
            )
            if rooms.count() != len(selected):
                raise ValueError("Une classe est inactive ou n’appartient pas à cette année.")
            # Canonical codes are stable per calendar month; never overwrite a
            # modified, inactive or conflicting existing schedule during a retry.
            codes = ["scolarite-" + day.strftime("%Y-%m") for day in dates]
            existing = list(FeeSchedule.objects.select_for_update().filter(
                school=school, year=year,
            ).filter(Q(classroom__isnull=True) | Q(classroom_id__in=selected)))
            by_key = {(row.classroom_id, row.code): row for row in existing}
            other_tuition = [row for row in existing if tuition_like(row) and row.code not in codes and row.active]
            if any(row.due_date is None or any(
                (row.due_date.year, row.due_date.month) == (day.year, day.month) for day in dates
            ) for row in other_tuition):
                return JsonResponse({"error": "Des tarifs de scolarité existants se chevauchent. Vérifiez-les avant de générer."}, status=409)
            pending = []
            unchanged = 0
            for classroom_id in selected:
                for day, code in zip(dates, codes):
                    row = by_key.get((classroom_id, code))
                    if by_key.get((None, code)) is not None:
                        return JsonResponse({"error": "Une mensualité générale existe déjà pour cette période."}, status=409)
                    if row is not None:
                        if not row.active or row.amount != amount or row.currency != "XAF" or row.due_date != day:
                            return JsonResponse({"error": "Une mensualité existe avec une autre configuration. Modifiez-la séparément."}, status=409)
                        unchanged += 1
                        continue
                    pending.append(FeeSchedule(school=school, year=year, classroom_id=classroom_id,
                        scope_key=str(classroom_id), code=code, label="Scolarité — " + day.strftime("%m/%Y"),
                        amount=amount, currency="XAF", due_date=day))
            FeeSchedule.objects.bulk_create(pending)
            if pending:
                log_event(school, request, "monthly_fee_schedules_generated", year.pk,
                    {"classes": len(selected), "months": codes, "created": len(pending), "amount_xaf": str(amount)})
        return JsonResponse({"created": len(pending), "unchanged": unchanged,
            "due_dates": [day.isoformat() for day in dates]}, status=201 if pending else 200)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except IntegrityError:
        return JsonResponse({"error": "Un tarif a été créé simultanément. Actualisez avant de réessayer."}, status=409)


@require_http_methods(["GET", "PATCH"])
@authorized
def schedule_detail(request, school_id, schedule_id):
    school, error = tariff_gate(request, school_id)
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
            row = FeeSchedule.objects.select_for_update().select_related("year").filter(school=school, pk=schedule_id).first()
            if row is None:
                return JsonResponse({"error": "Frais introuvable."}, status=404)
            if row.revision != data["revision"]:
                return JsonResponse({"error": "Conflit de version.", "revision": row.revision}, status=409)
            if not row.year.active or row.year.status == AcademicYear.STATUS_CLOSED:
                return JsonResponse({"error": "Année scolaire inactive ou clôturée."}, status=409)
            if "due_date" in changes and changes["due_date"] is not None and not (
                row.year.start_date <= changes["due_date"] <= row.year.end_date
            ):
                return JsonResponse({"error": "L’échéance doit être comprise dans l’année scolaire."}, status=422)
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
        rows = FeePayment.objects.select_related("charge").filter(
            school=school, charge_id=charge_id
        ).order_by("created_at", "pk")[:500]
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
    if method in ("cash", "simulation"):
        return JsonResponse({"error": "Code historique ou fictif interdit pour un nouvel encaissement. Choisissez « especes » pour des espèces réellement reçues."}, status=422)
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
            if method in CASH_METHODS:
                # Lock order matches the cash-closing endpoint, avoiding a race
                # between a cashier's last payment and the end-of-day snapshot.
                School.objects.select_for_update().get(pk=school.pk)
            charge = FeeCharge.objects.select_for_update().filter(school=school, pk=charge_id).first()
            if charge is None:
                return JsonResponse({"error": "Frais affecté introuvable."}, status=404)
            if classify_payment(method, charge.label) == "simulation":
                return JsonResponse({"error": "Paiement sur un frais explicitement DÉMO interdit en caisse réelle."}, status=422)
            previous = FeePayment.objects.filter(school=school, idempotency_key=idem).first()
            if previous:
                same = (previous.charge_id == charge.pk and previous.amount == amount
                    and previous.method == method and previous.reference == reference.strip()
                    and previous.paid_on == paid_on)
                if same:
                    return JsonResponse(payment_data(previous), status=200)
                return JsonResponse({"error": "Clé d'opération réutilisée avec des données différentes."}, status=409)
            if method in CASH_METHODS and cash_closed_for_recorder(
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
        if row.method in CASH_METHODS and cash_closed_for_recorder(school=school, day=row.paid_on, currency=row.currency, user=row.recorded_by):
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
@previewable_pdf
def receipt(request, school_id, payment_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    payment = FeePayment.objects.select_related(
        "charge__enrollment__student", "charge__enrollment__year",
        "charge__enrollment__classroom", "recorded_by",
    ).filter(school=school, pk=payment_id).first()
    if payment is None:
        return JsonResponse({"error": "Reçu introuvable."}, status=404)
    from .finance_document_pdf import render_school_financial_pdf, school_guardian, payment_evidence
    charge = payment.charge
    enrollment = charge.enrollment
    student = enrollment.student
    cancelled = FeePaymentVoid.objects.filter(payment=payment, school=school).exists()
    evidence = payment_evidence(payment.method, charge.label)
    remaining = (charge.amount - charge.scholarship_discount - cleared_total(charge))
    cashier = payment.recorded_by.get_username() if payment.recorded_by else ""
    response = render_school_financial_pdf(
        school=school, title="Reçu de paiement", receipt=True,
        reference="REC-" + payment.paid_on.strftime("%Y") + "-" + payment.pk.hex.upper(),
        issued_on=payment.created_at,
        student_name=f"{student.first_name} {student.last_name}".strip(),
        matricule=student.student_code, classroom=enrollment.classroom.name,
        year=enrollment.year.name, payer=school_guardian(student),
        rows=[(charge.label, payment.amount)], currency=payment.currency,
        total=payment.amount, balance=remaining, method=payment.method,
        external_reference=payment.reference, cashier=cashier,
        note="Encaissé le " + payment.paid_on.strftime("%d/%m/%Y") +
        (" • Ce paiement a été annulé et ne vaut plus preuve d'encaissement." if cancelled else ""),
        cancelled=cancelled, demo=evidence == "simulation",
        review_required=evidence == "legacy_unverified",
        filename=f"yem-recu-{payment.pk}.pdf",
    )
    response["X-YEM-Receipt-Class"] = classify_payment(payment.method, charge.label)
    return response


@require_GET
@authorized
@previewable_pdf
def invoice(request, school_id, charge_id):
    """Invoice of one actually-assessed school fee, never a payment receipt.

    The charge is immutable; the settlement section is a current account status.
    """
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    charge = FeeCharge.objects.select_related(
        "enrollment__student", "enrollment__year", "enrollment__classroom"
    ).filter(school=school, pk=charge_id).first()
    if charge is None:
        return JsonResponse({"error": "Frais facturé introuvable."}, status=404)
    from .finance_document_pdf import render_school_financial_pdf, school_guardian
    enrollment = charge.enrollment
    student = enrollment.student
    net = charge.amount - charge.scholarship_discount
    paid = cleared_total(charge)
    return render_school_financial_pdf(
        school=school, title="Facture scolaire", receipt=False,
        reference="FAC-" + charge.created_at.strftime("%Y") + "-" + charge.pk.hex.upper(),
        issued_on=charge.created_at,
        student_name=f"{student.first_name} {student.last_name}".strip(),
        matricule=student.student_code, classroom=enrollment.classroom.name,
        year=enrollment.year.name, payer=school_guardian(student),
        rows=[(charge.label, charge.amount)], currency=charge.currency,
        total=net, paid=paid, balance=net-paid, discount=charge.scholarship_discount,
        due_on=charge.due_date,
        note="Situation des règlements actualisée au " + timezone.localdate().strftime("%d/%m/%Y") +
        ". Le montant et la désignation des frais correspondent au barème figé lors de l'affectation.",
        filename=f"yem-facture-{charge.pk}.pdf",
    )
