"""Daily physical cash reconciliation for YEM schools.

Only actual cash declared by the employee is counted. This is not a bank or
mobile wallet reconciliation and does not invent a settlement confirmation.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import authorized

from .finance_models import CashClosing
from .finance_views import (
    CURRENCY_PATTERN, MAX_MONEY, MONEY_PATTERN, gate, iso_day, model_error,
)
from .finance_cash_policy import recorded_cash_total
from .models import School
from .views import log_event, parse_body


def counted_money(value):
    if type(value) not in (str, int) or not MONEY_PATTERN.fullmatch(str(value)):
        raise ValueError("Montant de caisse invalide : deux décimales maximum.")
    money = Decimal(str(value))
    if money < 0 or money > MAX_MONEY:
        raise ValueError("Le montant compté doit être compris dans les limites admises.")
    return money.quantize(Decimal("0.01"))


def closing_data(row):
    current = recorded_cash_total(
        school=row.school, day=row.day, currency=row.currency, user=row.submitted_by,
    )
    return {
        "id": str(row.pk), "day": row.day.isoformat(),
        "currency": row.currency, "expected": str(row.expected),
        "counted": str(row.counted), "difference": str(row.difference),
        "note": row.note, "submitted_by": row.submitted_by.username,
        "submitted_at": row.submitted_at.isoformat(),
        "status": "approved" if row.approved_at else "submitted",
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "approved_by": row.approved_by.username if row.approved_by else None,
        "approval_note": row.approval_note,
        "current_recorded_cash": str(current),
        "adjustment_since_submission": str(current - row.expected),
    }


@require_http_methods(["GET", "POST"])
@authorized
def cash_closings(request, school_id):
    permission = "school.finance.read" if request.method == "GET" else "school.finance.receive"
    school, error = gate(request, school_id, permission)
    if error is not None:
        return error
    if request.method == "GET":
        rows = CashClosing.objects.select_related(
            "school", "submitted_by", "approved_by"
        ).filter(school=school).order_by("-day", "-submitted_at")[:100]
        return JsonResponse({"closings": [closing_data(row) for row in rows]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"day", "currency", "counted", "note"}:
        return JsonResponse({"error": "Champs du contrôle de caisse invalides."}, status=422)
    currency = data["currency"]
    note = data["note"]
    if not isinstance(currency, str) or not CURRENCY_PATTERN.fullmatch(currency):
        return JsonResponse({"error": "Devise ISO invalide."}, status=422)
    if not isinstance(note, str) or len(note.strip()) > 500:
        return JsonResponse({"error": "Justification de caisse invalide."}, status=422)
    try:
        day = iso_day(data["day"])
        counted = counted_money(data["counted"])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    if day > timezone.localdate():
        return JsonResponse({"error": "Impossible de clôturer une journée future."}, status=422)

    try:
        with transaction.atomic():
            # Cash payment endpoints lock the same school before inserting a line.
            # No cash payment for this cashier/day/currency can race the snapshot.
            School.objects.select_for_update().get(pk=school.pk)
            if CashClosing.objects.filter(
                school=school, day=day, currency=currency, submitted_by=request.user,
            ).exists():
                return JsonResponse({"error": "Cette journée est déjà déclarée. Demandez un contrôle."}, status=409)
            expected = recorded_cash_total(
                school=school, day=day, currency=currency, user=request.user,
            )
            difference = counted - expected
            if difference and len(note.strip()) < 10:
                return JsonResponse({"error": "Un écart de caisse exige une justification d'au moins 10 caractères."}, status=422)
            row = CashClosing(
                school=school, day=day, currency=currency,
                expected=expected, counted=counted, difference=difference,
                note=note.strip(), submitted_by=request.user,
            )
            row.full_clean()
            row.save()
            log_event(school, request, "cash_closing_submitted", row.pk)
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Clôture déjà déclarée pour ce caissier et cette journée."}, status=409)
    return JsonResponse(closing_data(row), status=201)


@require_POST
@authorized
def approve_cash_closing(request, school_id, closing_id):
    school, error = gate(request, school_id, "school.finance.reverse")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"note"} or not isinstance(data["note"], str) or len(data["note"].strip()) > 500:
        return JsonResponse({"error": "Motif de contrôle invalide."}, status=422)
    try:
        with transaction.atomic():
            # Lock only the closing row: approved_by is nullable, and
            # PostgreSQL rejects FOR UPDATE on the nullable side of an outer join.
            row = CashClosing.objects.select_for_update(of=("self",)).select_related(
                "school", "submitted_by", "approved_by"
            ).filter(school=school, pk=closing_id).first()
            if row is None:
                return JsonResponse({"error": "Clôture introuvable."}, status=404)
            if row.approved_at:
                return JsonResponse({"error": "Caisse déjà contrôlée."}, status=409)
            if row.submitted_by_id == request.user.pk:
                return JsonResponse({"error": "Le déclarant ne peut pas approuver sa propre caisse."}, status=403)
            note = data["note"].strip()
            if row.difference and len(note) < 10:
                return JsonResponse({"error": "Un écart nécessite un motif de validation détaillé."}, status=422)
            row.approved_at = timezone.now()
            row.approved_by = request.user
            row.approval_note = note
            row.full_clean()
            row.save(update_fields=["approved_at", "approved_by", "approval_note"])
            log_event(school, request, "cash_closing_approved", row.pk)
    except ValidationError as exc:
        return model_error(exc)
    return JsonResponse(closing_data(row))
