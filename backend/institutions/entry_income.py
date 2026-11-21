"""Read-only income-origin reporting.

Admission cash is a separate ledger from assessed school fees. Never add these
figures to FeePayment totals without a verified cross-ledger reconciliation.
"""
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from .parent_payment_models import AdmissionCashReceipt


def admission_cash_income(school, year, as_of=None):
    """Count declared cash admissions, not PSP settlements or tuition payments.

    Each receipt is counted at most once, whether created through the parent
    journey (request) or directly by the school's cashier (application).
    """
    today = as_of or timezone.localdate()
    empty = {
        "currency": "XAF",
        "source": "admission_cash_receipt",
        "evidence": "manual_cash_declared",
        "revenue_certified": False,
        "total": "0.00",
        "count": 0,
        "today": "0.00",
        "this_month": "0.00",
        "demo_excluded": 0,
        "voided_excluded": 0,
        "future_dated_excluded": 0,
    }
    if year is None:
        return empty

    receipts = AdmissionCashReceipt.objects.filter(school=school).filter(
        Q(application__school=school, application__year=year)
        | Q(request__application__school=school, request__application__year=year)
    )
    valid = receipts.filter(is_demo=False, void__isnull=True, received_on__lte=today)
    month_start = today.replace(day=1)

    def total(qs):
        value = qs.aggregate(value=Sum("amount_xaf"))["value"] or 0
        return str(Decimal(value).quantize(Decimal("0.01")))

    return {
        **empty,
        "total": total(valid),
        "count": valid.count(),
        "today": total(valid.filter(received_on=today)),
        "this_month": total(valid.filter(received_on__gte=month_start)),
        "demo_excluded": receipts.filter(is_demo=True, void__isnull=True).count(),
        "voided_excluded": receipts.filter(void__isnull=False).count(),
        "future_dated_excluded": receipts.filter(
            is_demo=False, void__isnull=True, received_on__gt=today,
        ).count(),
    }
