"""A6b1: authenticated, read-only extracurricular cart quotation.

A quote is not an order, sale, invoice, school fee, debt, payment or cash event.
Unit prices are read exclusively from the school-scoped catalogue. Future
sales will snapshot these values in a separate immutable ledger after B's
migrations are integrated and tested.
"""
import json
from decimal import Decimal, InvalidOperation
from uuid import UUID

from accounts.views import authorized
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .academic_models import AcademicYear
from .entry_extras_catalog import SCOPE, PRICE_PATTERN, records
from .finance_views import gate
from .models import SchoolSetting

MAX_LINES = 30
MAX_QUANTITY = 1000
MAX_CART_AMOUNT = Decimal("9999999999.99")
CENT = Decimal("0.01")


def _error(message, status=422):
    return JsonResponse({"error": message}, status=status, headers={"Cache-Control": "no-store"})


@require_POST
@authorized
def extras_quote(request, school_id):
    school, denied = gate(request, school_id, "school.finance.read")
    if denied is not None:
        return denied
    if len(request.body) > 16384:
        return _error("Le panier est trop volumineux.", 413)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return _error("JSON invalide.", 400)
    if not isinstance(payload, dict) or set(payload) - {"academic_year", "items"}:
        return _error("Paramètres du devis invalides.")
    provided_items = payload.get("items")
    if not isinstance(provided_items, list) or not 1 <= len(provided_items) <= MAX_LINES:
        return _error("Le devis exige entre 1 et 30 lignes.")

    year = payload.get("academic_year") or None
    if year is not None:
        try:
            year = str(UUID(str(year)))
        except (ValueError, AttributeError, TypeError):
            return _error("Année scolaire invalide.")
        if not AcademicYear.objects.filter(pk=year, school=school).exists():
            return _error("Année scolaire introuvable dans cet établissement.")

    setting = SchoolSetting.objects.filter(school=school, scope_key=SCOPE).first()
    catalog = {
        str(item.get("id")): item
        for item in records(setting)
        if isinstance(item, dict) and item.get("id")
    }
    seen, lines, currency, total = set(), [], None, Decimal("0.00")

    for entry in provided_items:
        if not isinstance(entry, dict) or set(entry) != {"id", "quantity"}:
            return _error("Ligne du panier invalide.")
        try:
            item_id = str(UUID(str(entry["id"])))
        except (ValueError, TypeError, AttributeError):
            return _error("Référence article invalide.")
        quantity = entry["quantity"]
        if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
            return _error("Quantité entière entre 1 et 1 000 requise.")
        if item_id in seen:
            return _error("Un article ne peut figurer deux fois dans le panier.")
        seen.add(item_id)
        product = catalog.get(item_id)
        if not product or product.get("active") is not True:
            return _error("Article inexistant ou archivé pour cet établissement.", 404)
        if product.get("academic_year") and product["academic_year"] != year:
            return _error("Article limité à une autre année scolaire.")
        item_currency = product.get("currency")
        if currency is None:
            currency = item_currency
        if item_currency != currency:
            return _error("Devis multidevise refusé : préparez un devis par devise.")
        raw_price = product.get("unit_price")
        if not isinstance(raw_price, str) or not PRICE_PATTERN.fullmatch(raw_price):
            return _error("Tarif indisponible : corriger le catalogue.")
        try:
            unit_price = Decimal(raw_price).quantize(CENT)
        except InvalidOperation:
            return _error("Tarif indisponible : corriger le catalogue.")
        if unit_price <= 0:
            return _error("Tarif invalide : corriger le catalogue.")
        line_total = unit_price * quantity
        total += line_total
        if total > MAX_CART_AMOUNT:
            return _error("Le panier dépasse le plafond de devis.")
        lines.append({
            "catalog_item_id": item_id, "code": product["code"],
            "group": product["group"], "kind": product["kind"],
            "label": product["label"], "variant": product.get("variant", ""),
            "unit": product["unit"], "quantity": quantity,
            "unit_price": str(unit_price), "line_total": str(line_total),
            "currency": item_currency,
        })

    result = {
        "academic_year": year, "currency": currency, "lines": lines,
        "total": str(total.quantize(CENT)), "catalog_revision": setting.revision if setting else 0,
        "generated_at": timezone.now().isoformat(),
        "state": "estimation_non_enregistree",
        "recorded_sale": False, "recorded_payment": False, "stock_reserved": False,
        "payable": False,
        "notice": (
            "Devis indicatif, non enregistré : pas de facture, commande, créance, "
            "réservation de stock ni encaissement. Les prix devront être revérifiés "
            "lors de la création de la vente définitive."
        ),
    }
    return JsonResponse(result, headers={"Cache-Control": "no-store"})
