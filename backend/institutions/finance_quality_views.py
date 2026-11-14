"""Read-only classification of financial entries for reconciliation.

Evidence categories are deliberately conservative: a legacy code is NOT proof of
cash received; a payment row is not independently confirmed by a bank.
This route does not mutate, void, relabel or backfill financial records.
"""
from collections import defaultdict
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from accounts.views import authorized

from .academic_models import AcademicYear
from .finance_evidence import explicit_demo, classify_payment
from .finance_models import FeeCharge, FeePayment
from .finance_views import gate, uid

ZERO = Decimal("0.00")
def money(value):
    return str(value.quantize(Decimal("0.01")))


@never_cache
@require_GET
@authorized
def quality(request, school_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    requested_year = request.GET.get("year")
    year_id = None
    if requested_year is not None:
        year_id = uid(requested_year)
        if year_id is None or not AcademicYear.objects.filter(school=school, pk=year_id).exists():
            return JsonResponse({"error": "Année scolaire inconnue dans cet établissement."}, status=422)

    charges = FeeCharge.objects.filter(school=school)
    payments = FeePayment.objects.filter(school=school, void__isnull=True)
    if year_id:
        charges = charges.filter(enrollment__year_id=year_id)
        payments = payments.filter(charge__enrollment__year_id=year_id)

    def new_section():
        return {
            "explicit_demo_charges": {"count": 0, "net_amount": ZERO},
            "explicit_demo_payments": {"count": 0, "amount": ZERO},
            "legacy_cash_unverified": {"count": 0, "amount": ZERO},
            "cash_declared": {"count": 0, "amount": ZERO},
            "other_manual_unverified": {"count": 0, "amount": ZERO},
        }

    sections = defaultdict(new_section)
    for charge in charges.values("currency", "amount", "scholarship_discount", "label").iterator():
        if explicit_demo(charge["label"]):
            item = sections[charge["currency"]]["explicit_demo_charges"]
            item["count"] += 1
            item["net_amount"] += charge["amount"] - (charge["scholarship_discount"] or ZERO)

    for payment in payments.values(
        "currency", "amount", "method", "charge__label"
    ).iterator():
        kind = classify_payment(
            payment["method"], payment["charge__label"]
        )
        if kind == "simulation":
            category = "explicit_demo_payments"
        elif kind == "legacy_unverified":
            category = "legacy_cash_unverified"
        elif payment["method"] == "especes":
            category = "cash_declared"
        else:
            category = "other_manual_unverified"
        item = sections[payment["currency"]][category]
        item["count"] += 1
        item["amount"] += payment["amount"]

    return JsonResponse({
        "school": str(school.pk),
        "year": str(year_id) if year_id else None,
        "basis": "rapprochement_declarations_manuelles",
        "certified_revenue": False,
        "warning": (
            "Aucune écriture manuelle n'est une preuve bancaire indépendante. "
            "Les paiements historiques cash restent à justifier, sans reclassement automatique. "
            "Les tableaux financiers ordinaires conservent les écritures historiques tant que "
            "leur rapprochement n'est pas validé."
        ),
        "currencies": {
            currency: {
                key: {
                    field: money(value) if field in ("net_amount", "amount") else value
                    for field, value in group.items()
                }
                for key, group in data.items()
            }
            for currency, data in sorted(sections.items())
        },
    }, headers={"Cache-Control": "private, no-store"})
