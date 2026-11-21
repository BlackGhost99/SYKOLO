"""Reliable school finance summary, without summing unlike currencies.

This is a read-only manual ledger report. It does not certify PSP settlement.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from accounts.views import authorized

from .academic_models import AcademicYear
from .finance_models import FeeCharge, FeePayment
from .finance_views import gate, uid
from .finance_evidence import evidence_totals
from .entry_income import admission_cash_income, fee_entries_by_category
from .student_access import can_read_finance
from .student_models import Enrollment
from .views import refuse


ZERO = Decimal("0.00")


def as_money(value):
    return str(value.quantize(Decimal("0.01")))


@require_GET
@authorized
def summary(request, school_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error

    year_param = request.GET.get("year")
    year_id = None
    selected_year = None
    if year_param is not None:
        year_id = uid(year_param)
        if year_id is None:
            return JsonResponse({"error": "Année scolaire introuvable dans cet établissement."}, status=422)
        selected_year = AcademicYear.objects.filter(school=school, pk=year_id).first()
        if selected_year is None:
            return JsonResponse({"error": "Année scolaire introuvable dans cet établissement."}, status=422)

    charges = FeeCharge.objects.filter(school=school)
    payments = FeePayment.objects.filter(school=school, void__isnull=True)
    if year_id:
        charges = charges.filter(enrollment__year_id=year_id)
        payments = payments.filter(charge__enrollment__year_id=year_id)

    paid_by_charge = {
        row["charge_id"]: row["total"] or ZERO
        for row in payments.values("charge_id").annotate(total=Sum("amount"))
    }
    from .historical_finance import historical_credits
    opening = historical_credits(school.pk, charges.values("pk"))
    totals = defaultdict(lambda: {
        "billed": ZERO, "paid": ZERO, "historical_credit": ZERO, "balance": ZERO,
        "overdue": ZERO, "charges": 0, "overdue_charges": 0,
        "by_method": {},
    })
    today = timezone.localdate()
    for charge in charges.only("id", "currency", "amount", "scholarship_discount", "due_date").iterator():
        section = totals[charge.currency]
        paid = paid_by_charge.get(charge.pk, ZERO)
        credit = opening.get(charge.pk, ZERO)
        balance = charge.amount - charge.scholarship_discount - paid - credit
        section["historical_credit"] += credit
        section["billed"] += charge.amount - charge.scholarship_discount
        section["paid"] += paid
        section["balance"] += balance
        section["charges"] += 1
        if balance > ZERO and charge.due_date and charge.due_date < today:
            section["overdue"] += balance
            section["overdue_charges"] += 1

    by_method = payments.values("currency", "method").annotate(total=Sum("amount"))
    for item in by_method:
        totals[item["currency"]]["by_method"][item["method"]] = as_money(item["total"] or ZERO)

    evidence = evidence_totals(payments)
    return JsonResponse({
        "school": str(school.pk),
        "year": str(year_id) if year_id else None,
        "as_of": today.isoformat(),
        "basis": "encaissements_manuels",
        "revenue_certified": False,
        "note": ("Les totaux historiques billed/paid/balance correspondent aux écritures "
                 "comptables, et ne constituent ni des recettes certifiées ni une preuve bancaire. "
                 "Consultez evidence pour distinguer les simulations et les écritures cash non rapprochées."),
        "evidence": evidence,
        # Only a year-scoped request gets a category report. Without year,
        # the legacy summary aggregates all years and cannot be compared
        # with a single-year income breakdown.
        "entry_categories": fee_entries_by_category(school, selected_year, today)
            if selected_year is not None else None,
        "admission_cash": admission_cash_income(school, selected_year, today)
            if selected_year is not None else None,
        "entry_note": (
            "Ventilation par année scolaire. Frais d'inscription en caisse et "
            "tarifs d'inscription du registre sont deux sources NON cumulables "
            "avant rapprochement. Aucun montant n'est certifié."
            if selected_year is not None else
            "Ajoutez ?year=UUID pour obtenir la ventilation d'entrées d'une année."
        ),
        "currencies": {
            currency: {
                "billed": as_money(data["billed"]),
                "paid": as_money(data["paid"]),
                "historical_credit": as_money(data["historical_credit"]),
                "settled": as_money(data["paid"] + data["historical_credit"]),
                "balance": as_money(data["balance"]),
                "overdue": as_money(data["overdue"]),
                "charges": data["charges"],
                "overdue_charges": data["overdue_charges"],
                "by_method": data["by_method"],
            }
            for currency, data in sorted(totals.items())
        },
    }, headers={"Cache-Control": "no-store"})


@require_GET
@authorized
def finance_roster(request, school_id):
    """Répertoire de paiement : identité minimale et inscriptions, jamais les familles.

    Cette route remplace l'accès aux fichiers élèves depuis la caisse.
    """
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    if not can_read_finance(request.user, school):
        return refuse()
    qs = Enrollment.objects.filter(
        school=school, student__school=school, classroom__school=school,
        year__school=school,
    ).select_related("student").order_by("-year__start_date", "student__last_name", "id")[:1000]
    records = list(qs)
    pupils = {}
    for e in records:
        pupils[e.student_id] = {
            "id": str(e.student_id), "first_name": e.student.first_name,
            "last_name": e.student.last_name, "student_code": e.student.student_code,
        }
    return JsonResponse({
        "students": list(pupils.values()),
        "enrollments": [{
            "id": str(e.pk), "student": str(e.student_id),
            "classroom": str(e.classroom_id), "year": str(e.year_id),
            "enrolled_on": e.enrolled_on.isoformat(),
            "status": e.status, "active": e.active,
        } for e in records],
    }, headers={"Cache-Control": "no-store"})
