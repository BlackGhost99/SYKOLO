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


# Only explicit tariff-code conventions have an automatic category. Ambiguous
# codes are preserved in "a_classer" so an administrator can map them later.
EXTRASCOLAIRE_CODES = frozenset({
    "cantine", "transport", "uniforme", "restauration",
    "club", "activite", "sport", "sortie", "internat", "navette",
})
CATEGORIES = (
    ("scolarite", "Scolarité"),
    ("inscription_registre", "Inscription — frais liés aux élèves"),
    ("autre_scolaire", "Autres obligations scolaires"),
    ("extrascolaire", "Extrascolaire"),
    ("a_classer", "Autres frais à classer"),
    ("demo", "Démonstration — hors recettes réelles"),
)


def _category(code, charge_label="", method=""):
    """Classify only explicit fee codes; never infer from a display label."""
    from .finance_evidence import explicit_demo

    key = (code or "").strip().lower().replace("_", "-")
    frozen_label = (charge_label or "").strip().lower()
    bracketed_demo = frozen_label.startswith(("[démo]", "[demo]"))
    if key.startswith("demo-") or method == "simulation" or explicit_demo(charge_label) or bracketed_demo:
        return "demo"
    if key == "scolarite" or key.startswith(("scol-", "scolarite-", "tuition-")):
        return "scolarite"
    if key == "inscription" or key.startswith(("ins-", "inscription-")):
        return "inscription_registre"
    if any(key == prefix or key.startswith(prefix + "-") for prefix in EXTRASCOLAIRE_CODES):
        return "extrascolaire"
    return "a_classer"


def fee_entries_by_category(school, year, as_of=None):
    """Assessed fees and non-void manual payments by origin, read-only.

    No PSP/admissions source is added here. Each payment belongs to exactly one
    category and currency. The cash evidence is *declared*, never certified.
    """
    from collections import defaultdict
    from django.db.models import Count, F

    from .finance_models import FeeCharge, FeePayment
    from .finance_evidence import classify_payment
    from .entry_category_policy import fee_category_overrides, resolved_fee_category

    if year is None:
        return {"rows": [], "details": [], "note": "Aucune année scolaire sélectionnée."}

    today = as_of or timezone.localdate()
    start_month = today.replace(day=1)
    values = defaultdict(lambda: {
        "billed": Decimal("0.00"), "paid": Decimal("0.00"),
        "paid_today": Decimal("0.00"), "paid_month": Decimal("0.00"),
        "charges": 0, "payments": 0, "legacy_cash_unverified": Decimal("0.00"),
        "other_declared": Decimal("0.00"), "explicit_demo": Decimal("0.00"),
    })
    labels = dict(CATEGORIES)
    overrides = fee_category_overrides(school)

    def money(value):
        return str(value.quantize(Decimal("0.01")))

    charges = FeeCharge.objects.filter(
        school=school, enrollment__school=school,
        enrollment__year=year, schedule__school=school, schedule__year=year,
    )
    for item in charges.values("schedule_id", "schedule__code", "currency", "label").annotate(
        billed=Sum(F("amount") - F("scholarship_discount")),
        count=Count("pk"),
    ):
        code = item["schedule__code"]
        category = resolved_fee_category(item["schedule_id"], code, item["label"], overrides=overrides)
        totals = values[(category, item["currency"], code)]
        totals["billed"] += item["billed"] or Decimal("0.00")
        totals["charges"] += item["count"]

    payments = FeePayment.objects.filter(
        school=school, charge__school=school, charge__enrollment__school=school,
        charge__enrollment__year=year, charge__schedule__school=school,
        charge__schedule__year=year, void__isnull=True,
    )
    # Group by date, method and frozen label so demo evidence is not lost
    # when a FeeSchedule changes after the original posting.
    for item in payments.values(
        "charge__schedule_id", "charge__schedule__code", "charge__label", "currency", "method", "paid_on",
    ).annotate(paid=Sum("amount"), count=Count("pk")):
        code = item["charge__schedule__code"]
        category = resolved_fee_category(item["charge__schedule_id"], code, item["charge__label"], item["method"], overrides=overrides)
        totals = values[(category, item["currency"], code)]
        paid = item["paid"] or Decimal("0.00")
        totals["paid"] += paid
        totals["payments"] += item["count"]
        if item["paid_on"] == today:
            totals["paid_today"] += paid
        if start_month <= item["paid_on"] <= today:
            totals["paid_month"] += paid
        evidence = classify_payment(item["method"], item["charge__label"])
        evidence_name = (
            "explicit_demo" if category == "demo" or evidence == "simulation" else
            "legacy_cash_unverified" if evidence == "legacy_unverified" else
            "other_declared"
        )
        totals[evidence_name] += paid

    summary = defaultdict(lambda: {
        "billed": Decimal("0.00"), "paid": Decimal("0.00"),
        "paid_today": Decimal("0.00"), "paid_month": Decimal("0.00"),
        "charges": 0, "payments": 0, "legacy_cash_unverified": Decimal("0.00"),
        "other_declared": Decimal("0.00"), "explicit_demo": Decimal("0.00"),
    })
    details = []
    for (category, currency, code), totals in sorted(values.items()):
        subtotal = summary[(category, currency)]
        for key, value in totals.items():
            subtotal[key] += value
        details.append({
            "category": category, "currency": currency, "fee_code": code,
            "label": labels[category],
            **{key: money(value) if isinstance(value, Decimal) else value
               for key, value in totals.items()},
        })
    rows = []
    for (category, currency), totals in sorted(summary.items()):
        rows.append({
            "category": category, "label": labels[category], "currency": currency,
            "revenue_certified": False,
            **{key: money(value) if isinstance(value, Decimal) else value
               for key, value in totals.items()},
        })
    from .entry_receivables import category_receivables
    return {
        "rows": rows, "details": details,
        "receivables": category_receivables(school, year, today),
        "revenue_certified": False,
        "note": (
            "Ventilation des frais facturés et règlements manuels enregistrés. "
            "Les inscriptions en espèces de la caisse sont un registre séparé, "
            "non cumulable sans rapprochement. Aucun montant n'est certifié."
        ),
    }
