"""A6c physical inventory. OFF by default and completely distinct from school fees."""
import json
from uuid import UUID

from accounts.views import authorized
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from institutions.entry_extras_catalog import SCOPE, records
from institutions.finance_views import gate
from institutions.models import School, SchoolAudit, SchoolSetting

from .models import ExtraStock, ExtraStockMovement


def stock_error(message, status=422):
    return JsonResponse({"error": message}, status=status, headers={"Cache-Control": "no-store"})


def reserve_product_stock(*, school, snap_lines, sale, actor):
    """Called inside atomic sale transaction AFTER school row lock, before committing."""
    for line in snap_lines:
        if line["kind"] != "produit":
            continue
        item_id = UUID(str(line["catalog_item_id"]))
        stock = ExtraStock.objects.select_for_update().filter(
            school=school, catalog_item_id=item_id,
        ).first()
        quantity = line["quantity"]
        if stock is None or stock.quantity < quantity:
            raise ValueError(f"Stock insuffisant pour {line['code']}.")
        stock.quantity -= quantity
        stock.revision += 1
        stock.save(update_fields=["quantity", "revision", "updated_at"])
        ExtraStockMovement.objects.create(
            stock=stock, school=school, delta=-quantity,
            quantity_after=stock.quantity, movement_type="sale",
            reason=f"Vente {sale.reference}", operation_key=f"sale:{sale.pk}:{item_id}",
            sale=sale, actor=actor,
        )


@require_http_methods(["GET", "POST"])
@authorized
def inventory(request, school_id):
    permission = "school.finance.read" if request.method == "GET" else "school.finance.manage"
    school, denied = gate(request, school_id, permission)
    if denied is not None:
        return denied
    if request.method == "GET":
        return JsonResponse({
            "rows": [{"item_id": str(s.catalog_item_id), "quantity": s.quantity,
                      "revision": s.revision} for s in ExtraStock.objects.filter(school=school)],
            "stock_enabled": bool(getattr(settings, "YEM_EXTRA_STOCK_WRITES_ENABLED", False)),
        }, headers={"Cache-Control": "no-store"})
    if not getattr(settings, "YEM_EXTRA_STOCK_WRITES_ENABLED", False):
        return stock_error("Mouvements de stock désactivés.", 503)
    if len(request.body) > 4096:
        return stock_error("Requête trop volumineuse.", 413)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {
            "catalog_item_id", "quantity_delta", "reason", "operation_key", "revision"
        }:
            return stock_error("Paramètres de stock invalides.")
        item_id = UUID(str(data["catalog_item_id"]))
        delta = data["quantity_delta"]
        revision = data["revision"]
        reason = data["reason"]
        key = data["operation_key"]
        if type(delta) is not int or not -100000 <= delta <= 100000 or delta == 0:
            return stock_error("Variation entière non nulle requise.")
        if type(revision) is not int or revision < 0:
            return stock_error("Révision invalide.")
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 240:
            return stock_error("Motif d'inventaire obligatoire (10 à 240 caractères).")
        if not isinstance(key, str) or not 12 <= len(key) <= 120 or not all(
            c.isalnum() or c in "-_" for c in key
        ):
            return stock_error("Clé d'opération invalide.")
    except (ValueError, TypeError, KeyError, UnicodeDecodeError):
        return stock_error("Données d'inventaire invalides.")
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        previous = ExtraStockMovement.objects.filter(school=school, operation_key=key).first()
        if previous is not None:
            return stock_error("Clé d'opération de stock déjà utilisée.", 409)
        setting = SchoolSetting.objects.filter(school=school, scope_key=SCOPE).first()
        item = next((x for x in records(setting) if x.get("id") == str(item_id)), None)
        if not item or item.get("kind") != "produit":
            return stock_error("Produit physique inexistant dans cet établissement.")
        stock = ExtraStock.objects.select_for_update().filter(
            school=school, catalog_item_id=item_id,
        ).first()
        if stock is None:
            if revision != 0:
                return stock_error("Inventaire initial non créé : révision invalide.", 409)
            if delta < 0:
                return stock_error("Aucun stock disponible pour ce produit.")
            stock = ExtraStock.objects.create(school=school, catalog_item_id=item_id)
            stock = ExtraStock.objects.select_for_update().get(pk=stock.pk)
        if stock.revision != revision:
            return stock_error("Inventaire modifié par un autre agent.", 409)
        new_quantity = stock.quantity + delta
        if new_quantity < 0:
            return stock_error("Stock négatif interdit.")
        if new_quantity > 2_000_000_000:
            return stock_error("Quantité excessive.")
        stock.quantity = new_quantity
        stock.revision += 1
        stock.save(update_fields=["quantity", "revision", "updated_at"])
        movement = ExtraStockMovement.objects.create(
            school=school, stock=stock, delta=delta, quantity_after=new_quantity,
            movement_type="adjustment", reason=reason.strip(),
            operation_key=key, actor=request.user,
        )
        SchoolAudit.objects.create(
            school=school, actor=request.user, event="extras_stock_adjustment",
            subject=str(movement.pk), details={
                "catalog_item_id": str(item_id), "delta": delta,
                "quantity_after": new_quantity, "reason": reason.strip(),
            },
        )
        return JsonResponse({"quantity": new_quantity, "revision": stock.revision,
                             "movement_id": str(movement.pk)}, status=201,
                            headers={"Cache-Control": "no-store"})
