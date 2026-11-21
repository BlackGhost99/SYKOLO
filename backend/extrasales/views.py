"""School-isolated extracurricular sales & manual payment registry.

Writes are OFF by default. No PSP capture, no stock claim, no tuition ledger
mutation and no invoices/receipts represented as certified documents yet.
"""
import hashlib
import json
import uuid
from decimal import Decimal

from accounts.views import authorized
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from institutions.academic_models import AcademicYear
from institutions.entry_extras_catalog import SCOPE, records
from institutions.entry_extras_sale_rules import (
    ExtrasSaleRuleError, _money, snapshot_sale_lines,
)
from institutions.finance_views import gate
from institutions.models import School, SchoolAudit, SchoolSetting
from institutions.services import has_permission

from .models import ExtraPayment, ExtraSale, ExtraSaleLine


def error(message, status=422):
    return JsonResponse({"error": message}, status=status,
                        headers={"Cache-Control": "no-store"})


def parse_body(request, *, max_bytes=16384):
    if len(request.body) > max_bytes:
        raise ExtrasSaleRuleError("Requête trop volumineuse.")
    try:
        data = json.loads(request.body)
    except (UnicodeDecodeError, ValueError):
        raise ExtrasSaleRuleError("JSON invalide.") from None
    if not isinstance(data, dict):
        raise ExtrasSaleRuleError("Objet JSON requis.")
    return data


def enforce_keys(data, allowed, required):
    if set(data) - allowed or not set(required).issubset(data):
        raise ExtrasSaleRuleError("Champs du formulaire invalides.")


def key_value(data):
    value = data.get("idempotency_key")
    if not isinstance(value, str) or not 12 <= len(value) <= 80:
        raise ExtrasSaleRuleError("Clé d'idempotence de 12 à 80 caractères requise.")
    if not all(char.isalnum() or char in "-_" for char in value):
        raise ExtrasSaleRuleError("Clé d'idempotence invalide.")
    return value


def body_hash(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                                    sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sale_position(sale, *, include_buyer=False):
    paid = sale.manual_receipts.aggregate(sum=Sum("amount"))["sum"] or Decimal("0.00")
    remaining = max(Decimal("0.00"), sale.total - paid)
    data = {
        "id": str(sale.pk), "reference": sale.reference,
        "school": str(sale.school_id), "year": str(sale.year_id) if sale.year_id else None,
        "currency": sale.currency, "status": sale.status,
        "billed": f"{sale.total:.2f}", "received_manual_declared": f"{paid:.2f}",
        "received_provider_confirmed": "0.00",
        "outstanding": f"{remaining:.2f}", "revenue_certified": False,
        "receipts_count": sale.manual_receipts.count(),
        "created_at": sale.created_at.isoformat(),
        "notice": ("Règlements manuels déclarés seulement, sans certification bancaire. "
                   "Les montants ne sont pas comptés dans la scolarité."),
    }
    if include_buyer:
        data["buyer_label"] = sale.buyer_label
    return data


@require_http_methods(["GET", "POST"])
@authorized
def sales(request, school_id):
    perm = "school.finance.read" if request.method == "GET" else "school.finance.manage"
    school, denied = gate(request, school_id, perm)
    if denied is not None:
        return denied
    if request.method == "GET":
        qs = ExtraSale.objects.filter(school=school).order_by("-created_at", "-pk")
        year_value = request.GET.get("year")
        if year_value:
            try:
                year_uuid = uuid.UUID(year_value)
            except (TypeError, ValueError, AttributeError):
                return error("Année scolaire invalide.")
            if not AcademicYear.objects.filter(school=school, pk=year_uuid).exists():
                return error("Année scolaire étrangère à l'établissement.")
            qs = qs.filter(year_id=year_uuid)
        try:
            page = int(request.GET.get("page", "1"))
        except (TypeError, ValueError):
            return error("Pagination invalide.")
        if not 1 <= page <= 100000:
            return error("Pagination invalide.")
        total = qs.count()
        qs = qs[(page-1)*25:page*25]
        allow_buyer = has_permission(request.user, school, "school.finance.manage")
        return JsonResponse({
            "total": total, "page": page,
            "rows": [sale_position(row, include_buyer=allow_buyer) for row in qs],
            "category": "extrascolaire", "source": "extras_sales_only",
        }, headers={"Cache-Control":"no-store"})

    if not getattr(settings, "YEM_EXTRA_SALES_WRITES_ENABLED", False):
        return error("Ventes extrascolaires non activées sur cet environnement.", 503)
    try:
        data = parse_body(request)
        enforce_keys(data,
                     {"idempotency_key", "buyer_label", "academic_year", "catalog_revision", "items"},
                     {"idempotency_key", "buyer_label", "catalog_revision", "items"})
        key = key_value(data)
        label = data["buyer_label"]
        if not isinstance(label, str) or not 2 <= len(label.strip()) <= 120:
            raise ExtrasSaleRuleError("Acheteur obligatoire (2 à 120 caractères).")
        body_digest = body_hash(data)
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            existing = ExtraSale.objects.filter(school=school, idempotency_key=key).first()
            if existing:
                if existing.request_hash != body_digest:
                    return error("Cette clé d'opération a déjà servi avec un autre panier.", 409)
                return JsonResponse({"unchanged":True,"sale":sale_position(existing,include_buyer=True)},
                                    headers={"Cache-Control":"no-store"})
            year = None
            if data.get("academic_year"):
                try:
                    year_uuid = uuid.UUID(str(data["academic_year"]))
                except (ValueError, TypeError, AttributeError):
                    raise ExtrasSaleRuleError("Année scolaire invalide.") from None
                year = AcademicYear.objects.filter(school=school, pk=year_uuid).first()
                if year is None:
                    raise ExtrasSaleRuleError("Année scolaire étrangère à l'établissement.")
                if year.status == AcademicYear.STATUS_CLOSED:
                    raise ExtrasSaleRuleError("Année scolaire clôturée : nouvelle vente interdite.")
            setting = SchoolSetting.objects.select_for_update().filter(
                school=school, scope_key=SCOPE).first()
            catalog = records(setting)
            snap = snapshot_sale_lines(
                school_id=school.pk, academic_year=str(year.pk) if year else None,
                catalog_revision=setting.revision if setting else 0,
                expected_revision=data["catalog_revision"],
                catalog_items=catalog, selections=data["items"],
            )
            # Inventory management is a distinct feature. Never pretend to
            # have stock and sell physical items before stock control exists.
            if any(line["kind"] != "service" for line in snap["lines"]):
                raise ExtrasSaleRuleError(
                    "Ventes de produits bloquées jusqu'à activation du contrôle de stock.")
            sale = ExtraSale.objects.create(
                school=school, year=year, reference="EX-" + uuid.uuid4().hex[:16].upper(),
                buyer_label=label.strip(), currency=snap["currency"],
                total=Decimal(snap["total"]), catalog_revision=snap["catalog_revision"],
                idempotency_key=key, request_hash=body_digest, created_by=request.user)
            ExtraSaleLine.objects.bulk_create([
                ExtraSaleLine(sale=sale, position=number, catalog_item_id=line["catalog_item_id"],
                              code=line["code"], group=line["group"], kind=line["kind"],
                              label=line["label"], variant=line["variant"], unit=line["unit"],
                              quantity=line["quantity"], unit_price=Decimal(line["unit_price"]),
                              line_total=Decimal(line["line_total"]))
                for number, line in enumerate(snap["lines"], start=1)
            ])
            SchoolAudit.objects.create(
                school=school, actor=request.user, event="extras_sale_confirmed",
                subject=str(sale.pk),
                details={"reference":sale.reference,"total":snap["total"],
                         "currency":sale.currency, "catalog_revision":snap["catalog_revision"],
                         "line_count":len(snap["lines"])})
            return JsonResponse({"unchanged":False,"sale":sale_position(sale,include_buyer=True)},
                                status=201, headers={"Cache-Control":"no-store"})
    except ExtrasSaleRuleError as exc:
        return error(str(exc))


@require_POST
@authorized
def receive_manual(request, school_id, sale_id):
    school, denied = gate(request, school_id, "school.finance.receive")
    if denied is not None:
        return denied
    if not getattr(settings, "YEM_EXTRA_SALES_WRITES_ENABLED", False):
        return error("Encaissements extrascolaires non activés.", 503)
    try:
        data = parse_body(request, max_bytes=4096)
        enforce_keys(data,
                     {"idempotency_key", "amount", "method", "reference"},
                     {"idempotency_key", "amount", "method"})
        key = key_value(data)
        amount = _money(data["amount"], "Montant")
        method = data["method"]
        if method not in ("especes", "virement"):
            raise ExtrasSaleRuleError("Moyen manuel invalide ; SingPay exige un callback authentifié.")
        reference = data.get("reference", "")
        if not isinstance(reference, str) or len(reference.strip()) > 120:
            raise ExtrasSaleRuleError("Référence du versement invalide.")
        if method == "virement" and len(reference.strip()) < 3:
            raise ExtrasSaleRuleError("Référence du virement obligatoire.")
        body_digest = body_hash(data)
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            sale = ExtraSale.objects.select_for_update().filter(
                school=school, pk=sale_id, status="confirmed").first()
            if sale is None:
                return error("Vente introuvable dans cet établissement.", 404)
            old = ExtraPayment.objects.filter(school=school, idempotency_key=key).first()
            if old:
                if old.request_hash != body_digest or old.sale_id != sale.pk:
                    return error("Clé de règlement déjà utilisée pour une autre opération.", 409)
                return JsonResponse({"unchanged":True,"sale":sale_position(sale),
                                     "payment_id":str(old.pk)}, headers={"Cache-Control":"no-store"})
            if sale.year_id and sale.year.status == AcademicYear.STATUS_CLOSED:
                return error("Année scolaire clôturée : encaissement bloqué.", 422)
            received = sale.manual_receipts.aggregate(total=Sum("amount"))["total"] or Decimal("0")
            if received + amount > sale.total:
                return error("Règlement supérieur au solde de cette vente.", 422)
            receipt = ExtraPayment.objects.create(
                sale=sale, school=school, currency=sale.currency,
                amount=amount, paid_on=timezone.localdate(), method=method,
                reference=reference.strip(), evidence="manual_declared",
                idempotency_key=key, request_hash=body_digest, received_by=request.user)
            SchoolAudit.objects.create(
                school=school, actor=request.user, event="extras_payment_declared",
                subject=str(receipt.pk),
                details={"sale_id":str(sale.pk),"amount":f"{amount:.2f}",
                         "currency":sale.currency,"method":method,
                         "proof_level":"manual_declared"})
            return JsonResponse({"unchanged":False,"sale":sale_position(sale),
                                 "payment_id":str(receipt.pk)}, status=201,
                                headers={"Cache-Control":"no-store"})
    except ExtrasSaleRuleError as exc:
        return error(str(exc))
