"""Read-only reconciliation of every physical inventory balance with its movements."""
from accounts.views import authorized
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from institutions.finance_views import gate
from .models import ExtraStock


@require_GET
@authorized
def stock_audit(request, school_id):
    school, denied = gate(request, school_id, "school.finance.manage")
    if denied is not None:
        return denied
    try:
        page = int(request.GET.get("page", "1"))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Pagination invalide."}, status=422)
    if not 1 <= page <= 100000:
        return JsonResponse({"error": "Pagination invalide."}, status=422)
    qs = ExtraStock.objects.filter(school=school).order_by("catalog_item_id")
    count = qs.count()
    items = []
    anomalies = 0
    for stock in qs[(page - 1) * 50:page * 50]:
        movement_sum = stock.movements.aggregate(total=Sum("delta"))["total"] or 0
        mismatch = movement_sum != stock.quantity
        anomalies += int(mismatch)
        items.append({
            "catalog_item_id": str(stock.catalog_item_id),
            "quantity": stock.quantity, "movement_total": movement_sum,
            "difference": stock.quantity - movement_sum,
            "revision": stock.revision, "mismatch": mismatch,
        })
    return JsonResponse({
        "page": page, "total": count, "rows": items,
        "anomalies_on_page": anomalies,
        "scope": "school_extras_stock", "read_only": True,
    }, headers={"Cache-Control": "no-store"})
