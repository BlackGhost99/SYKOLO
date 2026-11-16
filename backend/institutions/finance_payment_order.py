"""Apply monthly tuition in chronological order within one enrollment."""
from decimal import Decimal
from itertools import groupby
from unicodedata import normalize

from django.db.models import Q, Sum

from .finance_evidence import explicit_demo
from .finance_models import FeeCharge


def tuition_like(code, label):
    text = normalize("NFKD", f"{code} {label}").encode("ascii", "ignore").decode().lower()
    return any(word in text for word in ("scolarite", "mensualite", "tuition"))


def monthly_charge(charge):
    return bool(charge.due_date and not explicit_demo(charge.label)
                and tuition_like(charge.schedule.code, charge.label))


def monthly_blockers(charges, balance):
    def month(charge):
        return charge.enrollment_id, charge.due_date.year, charge.due_date.month

    ordered = sorted(filter(monthly_charge, charges), key=lambda c: (month(c), c.due_date, c.pk))
    first_unpaid = {}
    blockers = {}
    for (enrollment, _, _), group in groupby(ordered, key=month):
        earlier = first_unpaid.get(enrollment)
        for charge in group:
            if earlier:
                blockers[charge.pk] = earlier.label
            if balance(charge) > 0:
                first_unpaid.setdefault(enrollment, charge)
    return blockers


def payment_order_error(targets, amounts):
    """Check the resulting balances, so a batch may cover consecutive months."""
    target = targets[0]
    if not any(monthly_charge(charge) for charge in targets):
        return ""
    charges = FeeCharge.objects.filter(
        school_id=target.school_id, enrollment_id=target.enrollment_id, due_date__isnull=False,
    ).select_related("schedule").annotate(
        cleared=Sum("payments__amount", filter=Q(payments__void__isnull=True), default=Decimal("0.00")),
    )
    blockers = monthly_blockers(charges, lambda charge: (
        charge.amount - charge.scholarship_discount - charge.cleared
        - amounts.get(charge.pk, Decimal("0.00"))
    ))
    for charge in targets:
        if charge.pk in blockers:
            return f"Réglez d’abord le solde de « {blockers[charge.pk]} » avant de payer cette mensualité."
    return ""
