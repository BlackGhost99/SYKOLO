"""Return stock from a confirmed physical sale without touching any money ledger."""
import json
from uuid import UUID

from accounts.views import authorized
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from institutions.finance_views import gate
from institutions.models import School, SchoolAudit
from .models import ExtraProductReturn, ExtraSaleLine, ExtraStock, ExtraStockMovement


@require_POST
@authorized
def return_product(request, school_id, sale_id):
    school, denied = gate(request, school_id, "school.finance.manage")
    if denied is not None:
        return denied
    if not getattr(settings, "YEM_EXTRA_STOCK_WRITES_ENABLED", False):
        return JsonResponse({"error": "Retours physiques désactivés."}, status=503)
    if len(request.body) > 4096:
        return JsonResponse({"error": "Requête trop volumineuse."}, status=413)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"line_id", "quantity", "reason", "operation_key"}:
            raise ValueError
        line_id = UUID(str(data["line_id"]))
        quantity = data["quantity"]
        reason = data["reason"]
        key = data["operation_key"]
        if type(quantity) is not int or not 1 <= quantity <= 100000:
            raise ValueError
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 240:
            raise ValueError
        if not isinstance(key, str) or not 12 <= len(key) <= 120 or not all(
            c.isalnum() or c in "-_" for c in key
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return JsonResponse({"error": "Paramètres de retour invalides."}, status=422)

    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        existing = ExtraProductReturn.objects.filter(school=school, operation_key=key).first()
        if existing is not None:
            if existing.sale_line_id != line_id or existing.quantity != quantity or existing.reason != reason.strip():
                return JsonResponse({"error": "Clé de retour déjà utilisée pour une autre opération."}, status=409)
            return JsonResponse({"unchanged": True, "return_id": str(existing.pk)},
                                headers={"Cache-Control": "no-store"})
        line = ExtraSaleLine.objects.select_related("sale").filter(
            sale__school=school, sale_id=sale_id, pk=line_id, kind="produit",
            sale__status="confirmed",
        ).first()
        if line is None:
            return JsonResponse({"error": "Ligne physique de vente introuvable."}, status=404)
        sold_stock_movement = ExtraStockMovement.objects.filter(
            school=school, sale=line.sale, movement_type="sale",
            stock__catalog_item_id=line.catalog_item_id,
        ).exists()
        if not sold_stock_movement:
            return JsonResponse({"error": "Aucune sortie de stock prouvée pour cette ligne."}, status=422)
        returned = line.product_returns.aggregate(total=Sum("quantity"))["total"] or 0
        if returned + quantity > line.quantity:
            return JsonResponse({"error": "La quantité retournée dépasse la quantité vendue."}, status=422)
        stock = ExtraStock.objects.select_for_update().filter(
            school=school, catalog_item_id=line.catalog_item_id,
        ).first()
        if stock is None or stock.quantity + quantity > 2_000_000_000:
            return JsonResponse({"error": "Stock introuvable ou quantité excessive."}, status=422)
        stock.quantity += quantity
        stock.revision += 1
        stock.save(update_fields=["quantity", "revision", "updated_at"])
        record = ExtraProductReturn.objects.create(
            school=school, sale_line=line, stock=stock,
            quantity=quantity, reason=reason.strip(), operation_key=key,
            actor=request.user,
        )
        ExtraStockMovement.objects.create(
            school=school, stock=stock, delta=quantity,
            quantity_after=stock.quantity, movement_type="return",
            reason=reason.strip(), operation_key=f"return:{record.pk}",
            sale=line.sale, actor=request.user,
        )
        SchoolAudit.objects.create(
            school=school, actor=request.user, event="extras_product_return",
            subject=str(record.pk),
            details={"sale_id": str(line.sale_id), "sale_line_id": str(line.pk),
                     "quantity": quantity, "stock_after": stock.quantity,
                     "reason": reason.strip(), "monetary_refund": False},
        )
        return JsonResponse({
            "return_id": str(record.pk), "unchanged": False,
            "quantity": quantity, "stock_after": stock.quantity,
            "monetary_refund": False,
        }, status=201, headers={"Cache-Control": "no-store"})
