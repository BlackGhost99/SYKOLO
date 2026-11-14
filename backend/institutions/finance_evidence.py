"""Conservative labels for manual school fee ledger entries.

A label or method is not a bank settlement proof. Classification is used only
for visibility and receipt wording; it never changes booked amounts or debt.
"""
import re

DEMO_LABEL = re.compile(r"^(?:d[eé]mo)(?:\s*[-—:]|\s*$|\s*\[)", re.IGNORECASE)


def explicit_demo(label):
    return bool(DEMO_LABEL.match((label or "").strip()))


def classify_payment(method, charge_label, schedule_label):
    if method == "simulation" or explicit_demo(charge_label) or explicit_demo(schedule_label):
        return "simulation"
    if method == "cash":
        return "legacy_unverified"
    return "manual_record"


def classify_batch(entries):
    """Use a mixed label if grouped receipts contain unlike evidence classes."""
    kinds = set(entries)
    return next(iter(kinds)) if len(kinds) == 1 else "mixed_review"
