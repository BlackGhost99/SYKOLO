"""Historical credits reduce obligations; they are never cash receipts."""
from decimal import Decimal

from django.db.models import Sum

from .finance_models import HistoricalFeeAdjustment

ZERO = Decimal("0.00")


def historical_credits(school_id, charges):
    """Use a school-scoped queryset or sequence of charge IDs, not a receipt join.

    Keeping the aggregates separate avoids multiplying amounts when a charge
    has several payments and a historical credit.
    """
    return dict(HistoricalFeeAdjustment.objects.filter(
        school_id=school_id, charge_id__in=charges, charge__school_id=school_id,
        batch__school_id=school_id, batch__status="approved",
    ).values("charge_id").annotate(total=Sum("amount")).values_list("charge_id", "total"))


def history_for_charge(charge):
    return historical_credits(charge.school_id, [charge.pk]).get(charge.pk, ZERO)
