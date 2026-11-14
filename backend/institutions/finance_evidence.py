"""Conservative labels for manual school fee ledger entries.

A label or method is not a bank settlement proof. Classification is used only
for visibility and receipt wording; it never changes booked amounts or debt.
"""
import re

DEMO_LABEL = re.compile(r"^(?:d[eé]mo)(?:\s*[-—:]|\s*$|\s*\[)", re.IGNORECASE)


def explicit_demo(label):
    return bool(DEMO_LABEL.match((label or "").strip()))


def classify_payment(method, charge_label, schedule_label=None):
    # FeeCharge.label is a frozen invoice snapshot; FeeSchedule.label is editable.
    # An edited tariff must never rewrite historical cash evidence.
    if method == "simulation" or explicit_demo(charge_label):
        return "simulation"
    if method == "cash":
        return "legacy_unverified"
    return "manual_record"


def classify_batch(entries):
    """Use a mixed label if grouped receipts contain unlike evidence classes."""
    kinds = set(entries)
    return next(iter(kinds)) if len(kinds) == 1 else "mixed_review"


def evidence_totals(payments):
    """Aggregate one school/year's posted payments by evidence, per currency.

    This does not certify a settlement or reclassify booked accounting values.
    Call with a school-scoped queryset excluding voided payments.
    """
    from collections import defaultdict
    from decimal import Decimal

    sections = defaultdict(lambda: {
        "explicit_demo": Decimal("0.00"),
        "legacy_cash_unverified": Decimal("0.00"),
        "other_declared": Decimal("0.00"),
    })
    for currency, amount, method, label in payments.values_list(
        "currency", "amount", "method", "charge__label"
    ).iterator():
        classification = classify_payment(method, label)
        category = ("explicit_demo" if classification == "simulation" else
                    "legacy_cash_unverified" if classification == "legacy_unverified"
                    else "other_declared")
        sections[currency][category] += amount
    return {
        currency: {key: str(value.quantize(Decimal("0.01")))
                   for key, value in groups.items()}
        for currency, groups in sections.items()
    }
