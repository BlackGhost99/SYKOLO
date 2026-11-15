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
    admission = AdmissionCashReceipt.objects.filter(
        school=school, recorded_by=user, received_on=day,
        is_demo=False, void__isnull=True,
    ).aggregate(total=Sum("amount_xaf"))["total"] or 0
    return ((total or Decimal("0.00")) + Decimal(admission)).quantize(Decimal("0.01"))
