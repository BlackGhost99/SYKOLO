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
    if year_param is not None:
        year_id = uid(year_param)
        if year_id is None or not AcademicYear.objects.filter(school=school, pk=year_id).exists():
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
    totals = defaultdict(lambda: {
        "billed": ZERO, "paid": ZERO, "balance": ZERO,
        "overdue": ZERO, "charges": 0, "overdue_charges": 0,
        "by_method": {},
    })
    today = timezone.localdate()
    for charge in charges.only("id", "currency", "amount", "due_date").iterator():
        section = totals[charge.currency]
        paid = paid_by_charge.get(charge.pk, ZERO)
        balance = charge.amount - paid
        section["billed"] += charge.amount
        section["paid"] += paid
        section["balance"] += balance
        section["charges"] += 1
        if balance > ZERO and charge.due_date and charge.due_date < today:
            section["overdue"] += balance
            section["overdue_charges"] += 1

    by_method = payments.values("currency", "method").annotate(total=Sum("amount"))
    for item in by_method:
        totals[item["currency"]]["by_method"][item["method"]] = as_money(item["total"] or ZERO)

    return JsonResponse({
        "school": str(school.pk),
        "year": str(year_id) if year_id else None,
        "as_of": today.isoformat(),
        "basis": "encaissements_manuels",
        "currencies": {
            currency: {
                "billed": as_money(data["billed"]),
                "paid": as_money(data["paid"]),
                "balance": as_money(data["balance"]),
                "overdue": as_money(data["overdue"]),
                "charges": data["charges"],
                "overdue_charges": data["overdue_charges"],
                "by_method": data["by_method"],
            }
            for currency, data in sorted(totals.items())
        },
    })
