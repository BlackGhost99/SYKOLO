"""Read-only outstanding school fees by explicit financial category.

No payments are written. Cash admissions, SingPay intents, sales and
external financing are separate ledgers and are NOT included.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .entry_category_policy import fee_category_overrides, resolved_fee_category
from .entry_income import CATEGORIES
from .finance_evidence import classify_payment
from .finance_models import FeeCharge, FeePayment

ZERO = Decimal("0.00")
COLUMNS = (
    "billed_net", "paid_declared", "outstanding", "overdue",
    "due_today", "future", "without_due_date", "overpayment_review",
)


def category_receivables(school, year, as_of=None):
    """Compute remaining receivables per charge before aggregation.

    Each net charge is offset by its non-void, non-demo manual payments dated
    on/before the report day. Negative balances become an explicit overpayment
    anomaly rather than concealing another pupil's unpaid balance.
    """
    today = as_of or timezone.localdate()
    if year is None:
        return {"rows": [], "as_of": today.isoformat(),
                "revenue_certified": False, "source": "fee_charge"}

    overrides = fee_category_overrides(school)
    scope = FeeCharge.objects.filter(
        school=school, enrollment__school=school, enrollment__year=year,
        schedule__school=school, schedule__year=year,
    )
    # Never offset one student's unpaid balance with a different charge.
    paid_by_charge = defaultdict(lambda: ZERO)
    posted = FeePayment.objects.filter(
        school=school, charge__school=school,
        charge__enrollment__school=school, charge__enrollment__year=year,
        charge__schedule__school=school, charge__schedule__year=year,
        void__isnull=True, paid_on__lte=today,
    )
    for entry in posted.values(
        "charge_id", "charge__label", "charge__schedule__code", "method",
    ).annotate(total=Sum("amount")).iterator(chunk_size=500):
        category = resolved_fee_category(
            None, entry["charge__schedule__code"], entry["charge__label"], entry["method"]
        )
        if category == "demo" or classify_payment(entry["method"], entry["charge__label"]) == "simulation":
            continue
        paid_by_charge[entry["charge_id"]] += entry["total"] or ZERO

    grouped = defaultdict(lambda: {key: ZERO for key in COLUMNS})
    labels = dict(CATEGORIES)
    for charge in scope.values(
        "id", "schedule_id", "schedule__code", "label", "currency",
        "amount", "scholarship_discount", "due_date",
    ).iterator(chunk_size=500):
        category = resolved_fee_category(
            charge["schedule_id"], charge["schedule__code"],
            charge["label"], overrides=overrides,
        )
        if category == "demo":
            continue
        ledger = grouped[(category, charge["currency"])]
        net = max(ZERO, charge["amount"] - charge["scholarship_discount"])
        paid = paid_by_charge[charge["id"]]
        due = max(ZERO, net - paid)
        surplus = max(ZERO, paid - net)
        ledger["billed_net"] += net
        ledger["paid_declared"] += paid
        ledger["outstanding"] += due
        ledger["overpayment_review"] += surplus
        if not due:
            continue
        due_date = charge["due_date"]
        if due_date is None:
            ledger["without_due_date"] += due
        elif due_date < today:
            ledger["overdue"] += due
        elif due_date == today:
            ledger["due_today"] += due
        else:
            ledger["future"] += due

    return {
        "as_of": today.isoformat(),
        "source": "fee_charge",
        "revenue_certified": False,
        "rows": [
            {"category": category, "label": labels[category], "currency": currency,
             **{k: str(v.quantize(Decimal("0.01"))) for k, v in values.items()}}
            for (category, currency), values in sorted(grouped.items())
        ],
        "note": (
            "Créances comptables nettes des bourses, réparties échéance par échéance. "
            "Les écritures annulées, de simulation et datées dans le futur ne diminuent "
            "pas les soldes. Les paiements restent déclaratifs et non certifiés. "
            "Le registre des inscriptions encaissées à la caisse n'est pas additionné."
        ),
    }
