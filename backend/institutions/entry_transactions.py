"""Read-only drilldown from fee category to payment and verified-document route.

Never mix admission-cash receipts, school fees, simulations or currencies.
Only finance readers have access to the immutable payment references.
"""
from uuid import UUID

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from accounts.views import authorized

from .academic_models import AcademicYear
from .entry_category_policy import fee_category_overrides, resolved_fee_category
from .entry_income import CATEGORIES
from .finance_evidence import classify_payment
from .finance_models import FeePayment
from .finance_views import gate


def _failure(error, status=422):
    return JsonResponse({"error":error},status=status,headers={"Cache-Control":"no-store"})


@require_GET
@authorized
def transactions(request, school_id):
    """An audited income ledger slice, not a bank-certified turnover report."""
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    try:
        year_id = UUID(request.GET.get("year", ""))
    except (ValueError, TypeError, AttributeError):
        return _failure("Année scolaire valide obligatoire.")
    year = AcademicYear.objects.filter(school=school, pk=year_id).first()
    if year is None:
        return _failure("Année scolaire étrangère ou introuvable.")
    category = request.GET.get("category", "")
    if category not in ("", *(key for key, _ in CATEGORIES)):
        return _failure("Catégorie invalide.")
    fee_code = request.GET.get("fee_code", "").strip()
    if len(fee_code) > 48:
        return _failure("Code tarif invalide.")
    currency = request.GET.get("currency", "").strip().upper()
    if currency and (len(currency) != 3 or not currency.isalpha() or not currency.isascii()):
        return _failure("Devise invalide.")
    try:
        page = int(request.GET.get("page", "1"))
    except (ValueError, TypeError):
        return _failure("Pagination invalide.")
    if page < 1 or page > 100000:
        return _failure("Pagination hors limite.")
    page_size = 25
    offset = (page - 1) * page_size
    overrides = fee_category_overrides(school)
    payments = FeePayment.objects.filter(
        school=school, charge__school=school,
        charge__enrollment__school=school, charge__enrollment__year=year,
        charge__schedule__school=school, charge__schedule__year=year,
        void__isnull=True,
    )
    if currency:
        payments = payments.filter(currency=currency)
    if fee_code:
        payments = payments.filter(charge__schedule__code=fee_code)
    payments = payments.select_related("charge__schedule").order_by("-paid_on", "-pk")
    total = 0
    result = []
    for row in payments.iterator(chunk_size=500):
        code = row.charge.schedule.code
        item_category = resolved_fee_category(row.charge.schedule_id, code,
            row.charge.label, row.method, overrides=overrides)
        if category and category != item_category:
            continue
        if offset <= total < offset + page_size:
            result.append({
                "id": str(row.pk), "date": row.paid_on.isoformat(),
                "amount": str(row.amount.quantize(__import__("decimal").Decimal("0.01"))),
                "currency": row.currency, "method": row.method,
                "category": item_category, "fee_code": code,
                "evidence": classify_payment(row.method, row.charge.label),
                "future_dated": row.paid_on > timezone.localdate(),
                "receipt_url": f"/api/v1/schools/{school.pk}/finance/payments/{row.pk}/receipt",
                "batch_id": str(row.batch_id) if row.batch_id else None,
            })
        total += 1

    return JsonResponse({
        "year": str(year.pk), "source": "fee_payment", "read_only": True,
        "revenue_certified": False,
        "note": ("Transactions scolaires manuelles, hors annulations. Les inscriptions encaissées "
                 "à la caisse relèvent d'un registre distinct. Les démonstrations ne sont pas des recettes réelles."),
        "filters": {"category": category, "currency": currency, "fee_code": fee_code},
        "rows": result, "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1)//page_size,
    },headers={"Cache-Control":"no-store"})
