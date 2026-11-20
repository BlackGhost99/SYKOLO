"""Explicit cash-only boundaries, shared by manual and grouped payments.

Receipt time, declared payment date and PSP settlement must not be conflated.
Daily closings use the cashier's declared receipt date and currency.
"""
from decimal import Decimal
from django.db.models import Sum
from .finance_models import CashClosing, FeePayment
from .parent_payment_models import AdmissionCashReceipt
from .finance_evidence import classify_payment

# Only "especes" certifies a cashier declaration. Legacy "cash" may be fictitious.
CASH_METHODS = ("especes",)
LEGACY_UNVERIFIED_METHODS = ("cash", "simulation")


def cash_closed_for_recorder(*, school, day, currency, user):
    return CashClosing.objects.filter(
        school=school, day=day, currency=currency, submitted_by=user,
    ).exists()


def recorded_cash_total(*, school, day, currency, user):
    # A DEMO fee can carry an historical "especes" method; do not treat it
    # as physical cash even if a former import used that method.
    entries = FeePayment.objects.filter(
        school=school, recorded_by=user, paid_on=day,
        currency=currency, method__in=CASH_METHODS, void__isnull=True,
    ).values_list("amount", "method", "charge__label")
    total = sum((
        amount for amount, method, label in entries.iterator()
        if classify_payment(method, label) != "simulation"
    ), Decimal("0.00"))
    # Admission receipts are denominated in XAF only. Never mix them into
    # an EUR (or any other currency) cash reconciliation.
    admission = 0
    if currency == "XAF":
        admission = AdmissionCashReceipt.objects.filter(
            school=school, recorded_by=user, received_on=day,
            is_demo=False, void__isnull=True,
        ).aggregate(total=Sum("amount_xaf"))["total"] or 0
    return ((total or Decimal("0.00")) + Decimal(admission)).quantize(Decimal("0.01"))


def unclosed_cash_days(*, school, start, end):
    """Declared cash receipts without a closing, grouped by cashier/day/currency."""
    totals = {}
    names = {}
    entries = FeePayment.objects.filter(
        school=school, paid_on__range=(start, end), method__in=CASH_METHODS,
        void__isnull=True,
    ).values("paid_on", "currency", "recorded_by_id", "recorded_by__username",
             "method", "charge__label").annotate(total=Sum("amount"))
    for entry in entries.iterator():
        if classify_payment(entry["method"], entry["charge__label"]) == "simulation":
            continue
        key = (entry["paid_on"], entry["currency"], entry["recorded_by_id"])
        totals[key] = totals.get(key, Decimal("0")) + entry["total"]
        names[key] = entry["recorded_by__username"]
    admissions = AdmissionCashReceipt.objects.filter(
        school=school, received_on__range=(start, end), is_demo=False, void__isnull=True,
    ).values("received_on", "recorded_by_id", "recorded_by__username").annotate(total=Sum("amount_xaf"))
    for entry in admissions.iterator():
        key = (entry["received_on"], "XAF", entry["recorded_by_id"])
        totals[key] = totals.get(key, Decimal("0")) + Decimal(entry["total"])
        names[key] = entry["recorded_by__username"]
    closed = set(CashClosing.objects.filter(school=school, day__range=(start, end))
                 .values_list("day", "currency", "submitted_by_id"))
    return [{"day": key[0].isoformat(), "currency": key[1], "agent": names[key],
             "expected": format(totals[key], ".2f")}
            for key in sorted(totals, key=lambda k: (k[0], k[1], str(k[2])), reverse=True)
            if key not in closed and totals[key] > 0]
