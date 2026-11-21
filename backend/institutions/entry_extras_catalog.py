"""Optional extracurricular income catalogue (A6a).

This is master data, not a cash register, invoice, stock system, or payment.
No expenses, salary, tuition liabilities or historical money are touched.
"""
import json
import re
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from accounts.views import authorized
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .academic_models import AcademicYear
from .finance_views import gate
from .models import School, SchoolAudit, SchoolSetting

SCOPE = "income.extras_catalog.v1"
GROUPS = (
    ("B01", "Uniformes et habillement"),
    ("B02", "Fournitures et manuels"),
    ("B03", "Cantine et restauration"),
    ("B04", "Transport scolaire"),
    ("B05", "Activités et événements"),
    ("B06", "Cours complémentaires"),
    ("B07", "Internat et services"),
    ("B08", "Services administratifs complémentaires"),
)
MAX_ITEMS = 300
CODE_PATTERN = re.compile(r"[A-Z][A-Z0-9-]{1,29}\Z")
PRICE_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?\Z")


def reject(message, status=422, revision=None):
    body = {"error": message}
    if revision is not None:
        body["revision"] = revision
    return JsonResponse(body, status=status, headers={"Cache-Control": "no-store"})


def records(setting):
    values = setting.values if setting and isinstance(setting.values, dict) else {}
    items = values.get("items", [])
    return items if isinstance(items, list) else []


def _text(value, length, label, required=False):
    if not isinstance(value, str) or len(value.strip()) > length:
        raise ValueError(label + " invalide.")
    result = value.strip()
    if required and not result:
        raise ValueError(label + " obligatoire.")
    return result


def validated_item(school, incoming, existing):
    if not isinstance(incoming, dict):
        raise ValueError("Produit ou prestation invalide.")
    allowed = {"id", "code", "group", "kind", "label", "subcategory", "variant",
               "unit", "unit_price", "currency", "academic_year", "active"}
    if set(incoming) - allowed:
        raise ValueError("Champs du catalogue non autorisés.")
    code = _text(incoming.get("code", ""), 30, "Code", True).upper()
    if not CODE_PATTERN.fullmatch(code) or code.startswith(("DEMO-", "SCOL-", "INS-")):
        raise ValueError("Code produit invalide ou réservé.")
    group = incoming.get("group")
    if group not in dict(GROUPS):
        raise ValueError("Famille extrascolaire invalide.")
    kind = incoming.get("kind")
    if kind not in ("produit", "service"):
        raise ValueError("Nature produit/service invalide.")
    label = _text(incoming.get("label", ""), 120, "Désignation", True)
    subcategory = _text(incoming.get("subcategory", ""), 80, "Sous-catégorie")
    variant = _text(incoming.get("variant", ""), 80, "Variante")
    unit = _text(incoming.get("unit", "unité"), 30, "Unité", True)
    currency = incoming.get("currency", "XAF")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("Devise invalide.")
    amount = incoming.get("unit_price")
    if not isinstance(amount, str) or not PRICE_PATTERN.fullmatch(amount):
        raise ValueError("Montant décimal positif requis, sans nombre flottant.")
    try:
        price = Decimal(amount)
    except InvalidOperation:
        raise ValueError("Prix invalide.") from None
    if price <= 0:
        raise ValueError("Prix unitaire strictement positif requis.")
    active = incoming.get("active", True)
    if type(active) is not bool:
        raise ValueError("État actif/inactif invalide.")

    year_value = incoming.get("academic_year") or None
    if year_value is not None:
        try:
            year_id = UUID(str(year_value))
        except (TypeError, ValueError, AttributeError):
            raise ValueError("Année scolaire invalide.") from None
        if not AcademicYear.objects.filter(school=school, pk=year_id).exists():
            raise ValueError("Année scolaire introuvable dans cet établissement.")
        year_value = str(year_id)

    if existing and (existing["code"] != code or existing["group"] != group):
        raise ValueError("Code et famille immuables : archivez et recréez un article.")
    return {
        "id": existing["id"] if existing else str(uuid4()), "code": code,
        "group": group, "kind": kind, "label": label,
        "subcategory": subcategory, "variant": variant, "unit": unit,
        "unit_price": str(price.quantize(Decimal("0.01"))),
        "currency": currency, "academic_year": year_value, "active": active,
    }


@require_http_methods(["GET", "POST"])
@authorized
def extras_catalog(request, school_id):
    permission = "school.finance.read" if request.method == "GET" else "school.finance.manage"
    school, error = gate(request, school_id, permission)
    if error is not None:
        return error
    if request.method == "GET":
        setting = SchoolSetting.objects.filter(school=school, scope_key=SCOPE).first()
        return JsonResponse({
            "revision": setting.revision if setting else 0,
            "groups": [{"code": code, "label": label} for code, label in GROUPS],
            "items": records(setting),
            "source": "extras_catalog_config",
            "sales_recorded": False,
            "notice": ("Catalogue de prix uniquement : aucune vente, créance, facture, "
                       "stock ou entrée de caisse n'est enregistrée ici."),
        }, headers={"Cache-Control": "no-store"})
    if len(request.body) > 16384:
        return reject("Requête trop volumineuse.", 413)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return reject("JSON invalide.", 400)
    if not isinstance(payload, dict) or set(payload) - {"revision", "reason", "action", "item"}:
        return reject("Paramètres du catalogue invalides.")
    revision = payload.get("revision")
    if type(revision) is not int or revision < 0:
        return reject("Révision du catalogue invalide.")
    reason = payload.get("reason")
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 240:
        return reject("Justification requise (10 à 240 caractères).")
    action = payload.get("action")
    if action not in ("upsert", "archive"):
        return reject("Action de catalogue invalide.")
    incoming = payload.get("item")
    if not isinstance(incoming, dict):
        return reject("Article invalide.")
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        setting = SchoolSetting.objects.select_for_update().filter(
            school=school, scope_key=SCOPE,
        ).first()
        previous_revision = setting.revision if setting else 0
        if previous_revision != revision:
            return reject("Le catalogue a été modifié ailleurs.", 409, previous_revision)
        items = list(records(setting))
        identity = incoming.get("id")
        if identity not in (None, ""):
            try:
                identity = str(UUID(str(identity)))
            except (ValueError, TypeError, AttributeError):
                return reject("Identifiant d'article invalide.")
        existing = next((record for record in items if record.get("id") == identity), None)
        if identity and existing is None:
            return reject("Article introuvable dans cet établissement.", 404)
        if action == "archive":
            if existing is None:
                return reject("Article introuvable dans cet établissement.", 404)
            changed = {**existing, "active": False}
        else:
            if existing is None and len(items) >= MAX_ITEMS:
                return reject("Catalogue limité à 300 articles.")
            try:
                changed = validated_item(school, incoming, existing)
            except ValueError as ex:
                return reject(str(ex))
            if any(
                row.get("code", "").upper() == changed["code"] and row.get("id") != changed["id"]
                for row in items
            ):
                return reject("Un article possède déjà ce code.")
        if existing == changed:
            return JsonResponse({"unchanged": True, "revision": revision, "item": changed},
                                headers={"Cache-Control": "no-store"})
        items = [row for row in items if row.get("id") != changed["id"]] + [changed]
        if setting is None:
            setting = SchoolSetting(
                school=school, scope_key=SCOPE,
                scope={"module": "income", "kind": "extras_catalog"}, revision=1,
            )
        else:
            setting.revision += 1
        setting.values = {"items": items}
        setting.full_clean()
        setting.save()
        SchoolAudit.objects.create(
            school=school, actor=request.user, event="income_extras_catalog",
            subject=changed["id"],
            details={"action": action, "code": changed["code"],
                     "previous": existing, "current": changed,
                     "reason": reason.strip(), "revision": setting.revision},
        )
        return JsonResponse({"revision": setting.revision, "item": changed,
                             "unchanged": False}, status=201 if existing is None else 200,
                            headers={"Cache-Control": "no-store"})
