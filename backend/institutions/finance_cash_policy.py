"""Explicit cash-only boundaries, shared by manual and grouped payments.

Receipt time, declared payment date and PSP settlement must not be conflated.
Daily closings use the cashier's declared receipt date and currency.
"""
from decimal import Decimal
from django.db.models import Sum
from .finance_models import CashClosing, FeePayment
from .parent_payment_models import AdmissionCashReceipt

# Only "especes" certifies a cashier declaration. Legacy "cash" may be fictitious.
CASH_METHODS = ("especes",)
LEGACY_UNVERIFIED_METHODS = ("cash", "simulation")


def cash_closed_for_recorder(*, school, day, currency, user):
    return CashClosing.objects.filter(
        school=school, day=day, currency=currency, submitted_by=user,
    ).exists()


def recorded_cash_total(*, school, day, currency, user):
    total = FeePayment.objects.filter(
        school=school, recorded_by=user, paid_on=day,
        currency=currency, method__in=CASH_METHODS, void__isnull=True,
    ).aggregate(total=Sum("amount"))["total"]
    admission = AdmissionCashReceipt.objects.filter(
        school=school, recorded_by=user, received_on=day,
        is_demo=False, void__isnull=True,
    ).aggregate(total=Sum("amount_xaf"))["total"] or 0
    return ((total or Decimal("0.00")) + Decimal(admission)).quantize(Decimal("0.01"))
