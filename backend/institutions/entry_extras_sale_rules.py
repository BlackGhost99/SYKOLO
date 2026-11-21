"""A6b2 financial rules for future durable extracurricular sales.

Pure, deterministic and intentionally NOT wired to an API or model yet.
The expense stream owns migrations 0082–0085 on an unmerged branch.
No money may be recorded through this module until a separately migrated,
transactional sale/payment ledger exists.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID
import re

CENT = Decimal("0.01")
MAX_TOTAL = Decimal("9999999999.99")
PRICE_FORMAT = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?\Z")
MAX_ROWS = 30
MAX_QTY = 1000


class ExtrasSaleRuleError(ValueError):
    """Invalid operation that must never create a sale/payment posting."""


def _uuid(value, field):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ExtrasSaleRuleError(f"{field} invalide.") from None


def _money(value, field, *, positive=True):
    if not isinstance(value, str) or not PRICE_FORMAT.fullmatch(value):
        raise ExtrasSaleRuleError(f"{field} doit être une chaîne décimale à deux centimes.")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ExtrasSaleRuleError(f"{field} invalide.") from None
    if positive and amount <= 0:
        raise ExtrasSaleRuleError(f"{field} doit être strictement positif.")
    if amount > MAX_TOTAL:
        raise ExtrasSaleRuleError(f"{field} dépasse le plafond autorisé.")
    return amount.quantize(CENT)


def _currency(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value):
        raise ExtrasSaleRuleError("Devise invalide.")
    return value


def snapshot_sale_lines(*, school_id, academic_year, catalog_revision,
                        expected_revision, catalog_items, selections):
    """Reprice all lines from trusted school catalogue. Never persist.

    Snapshot output is suitable for writing into an immutable SQL sale record,
    only by a future transaction that checks the revision under row lock.
    """
    school_id = _uuid(school_id, "Établissement")
    if academic_year is not None:
        academic_year = _uuid(academic_year, "Année scolaire")
    if type(catalog_revision) is not int or type(expected_revision) is not int:
        raise ExtrasSaleRuleError("Révision du catalogue obligatoire.")
    if expected_revision != catalog_revision:
        raise ExtrasSaleRuleError("Prix modifiés : reconstruisez le devis.")
    if not isinstance(catalog_items, (list, tuple)):
        raise ExtrasSaleRuleError("Catalogue non disponible.")
    if not isinstance(selections, list) or not 1 <= len(selections) <= MAX_ROWS:
        raise ExtrasSaleRuleError("La vente doit comporter entre 1 et 30 lignes.")

    indexed = {row["id"]: row for row in catalog_items if isinstance(row, dict) and "id" in row}
    lines, total, currency, seen = [], Decimal("0.00"), None, set()
    for row in selections:
        if not isinstance(row, dict) or set(row) != {"id", "quantity"}:
            raise ExtrasSaleRuleError("Ligne de vente invalide.")
        item_id = _uuid(row["id"], "Article")
        quantity = row["quantity"]
        if type(quantity) is not int or not 1 <= quantity <= MAX_QTY:
            raise ExtrasSaleRuleError("Quantité entière de 1 à 1 000 requise.")
        if item_id in seen:
            raise ExtrasSaleRuleError("Ligne article en doublon.")
        seen.add(item_id)
        article = indexed.get(item_id)
        if article is None or article.get("active") is not True:
            raise ExtrasSaleRuleError("Article inconnu ou archivé.")
        if article.get("academic_year") and article["academic_year"] != academic_year:
            raise ExtrasSaleRuleError("Tarif d'une autre année scolaire.")
        row_currency = _currency(article.get("currency"))
        if currency is not None and currency != row_currency:
            raise ExtrasSaleRuleError("Une vente ne peut pas mélanger les devises.")
        currency = row_currency
        unit_price = _money(article.get("unit_price"), "Prix catalogue")
        line_total = unit_price * quantity
        total += line_total
        if total > MAX_TOTAL:
            raise ExtrasSaleRuleError("Plafond de vente dépassé.")
        lines.append({
            "catalog_item_id": item_id, "code": str(article["code"]),
            "group": str(article["group"]), "kind": str(article["kind"]),
            "label": str(article["label"]), "variant": str(article.get("variant") or ""),
            "unit": str(article["unit"]), "quantity": quantity,
            "unit_price": f"{unit_price:.2f}", "line_total": f"{line_total:.2f}",
            "currency": currency,
        })
    return {
        "school_id": school_id, "academic_year": academic_year,
        "catalog_revision": catalog_revision, "currency": currency,
        "lines": lines, "total": f"{total:.2f}",
        "status": "snapshot_prepared_not_posted",
    }


def summarize_sale_payments(*, sale_id, school_id, currency, sale_total,
                            payments, as_of):
    """Read-only financial math, no fake receipts or cross-invoice offsets.

    A payment row is from the future immutable ledger. Only settled/reconciled
    rows whose settlement day is <= as_of count as received; voids do not.
    proof_level='manual_declared' remains separate from
    'provider_confirmed'. Pending/unconfirmed PSP attempts are not revenue.
    """
    sale_id = _uuid(sale_id, "Vente")
    school_id = _uuid(school_id, "Établissement")
    currency = _currency(currency)
    billed = _money(sale_total, "Total facturé")
    if not isinstance(as_of, date) or isinstance(as_of, type(None)):
        raise ExtrasSaleRuleError("Date de contrôle invalide.")
    if not isinstance(payments, (list, tuple)):
        raise ExtrasSaleRuleError("Paiements invalides.")
    seen = set()
    declared, confirmed, pending = Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    for record in payments:
        if not isinstance(record, dict):
            raise ExtrasSaleRuleError("Écriture de paiement invalide.")
        payment_id = _uuid(record.get("id"), "Paiement")
        if payment_id in seen:
            raise ExtrasSaleRuleError("Écriture de paiement dupliquée.")
        seen.add(payment_id)
        if _uuid(record.get("school_id"), "Établissement du paiement") != school_id:
            raise ExtrasSaleRuleError("Paiement d'un autre établissement.")
        if _uuid(record.get("sale_id"), "Vente du paiement") != sale_id:
            raise ExtrasSaleRuleError("Paiement d'une autre vente.")
        if _currency(record.get("currency")) != currency:
            raise ExtrasSaleRuleError("Devise du paiement incompatible.")
        amount = _money(record.get("amount"), "Montant du paiement")
        if type(record.get("reversed", False)) is not bool:
            raise ExtrasSaleRuleError("État d'annulation invalide.")
        if record.get("reversed", False):
            continue
        level = record.get("proof_level")
        status = record.get("status")
        if status not in {"pending", "settled"} or level not in {"manual_declared", "provider_confirmed"}:
            raise ExtrasSaleRuleError("Statut ou preuve du paiement invalide.")
        when = record.get("paid_on")
        if not isinstance(when, date):
            raise ExtrasSaleRuleError("Date du paiement invalide.")
        if status == "pending" or when > as_of:
            pending += amount
        elif level == "manual_declared":
            declared += amount
        else:
            confirmed += amount
    received = declared + confirmed
    outstanding = max(Decimal("0.00"), billed - received)
    overpayment = max(Decimal("0.00"), received - billed)
    return {
        "currency": currency, "billed": f"{billed:.2f}",
        "received_declared": f"{declared:.2f}",
        "received_provider_confirmed": f"{confirmed:.2f}",
        "received_total": f"{received:.2f}",
        "pending_not_revenue": f"{pending:.2f}",
        "outstanding": f"{outstanding:.2f}",
        "overpayment_review": f"{overpayment:.2f}",
        "contains_manual_declarations": declared > 0,
        "only_provider_confirmed_receipts": received > 0 and declared == 0,
        "source": "read_only_ledger_rules",
    }
