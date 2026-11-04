"""Explicit cash-only boundaries, shared by manual and grouped payments.

Receipt time, declared payment date and PSP settlement must not be conflated.
Daily closings use the cashier's declared receipt date and currency.
"""
from decimal import Decimal
from django.db.models import Sum
from .finance_models import CashClosing, FeePayment


def cash_closed_for_recorder(*, school, day, currency, user):
    return CashClosing.objects.filter(
        school=school, day=day, currency=currency, submitted_by=user,
    ).exists()


def recorded_cash_total(*, school, day, currency, user):
    total = FeePayment.objects.filter(
        school=school, recorded_by=user, paid_on=day,
        currency=currency, method="especes", void__isnull=True,
    ).aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0.00")
