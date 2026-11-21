"""School-scoped, audit-trailed fee classification for the ENTRIES workstream.

Uses existing SchoolSetting / SchoolAudit tables: no new migrations and no
outflow, treasury, inventory or payment rows are written. This first phase
classifies assessed school fees, NOT generic revenue or capital movements.
"""
from uuid import UUID

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .finance_views import gate
from .finance_models import FeeCharge, FeeSchedule
from .models import School, SchoolAudit, SchoolSetting

POLICY_SCOPE = "income.fee_classification.v1"
PERMITTED_FEE_CATEGORIES = (
    ("scolarite", "Scolarité principale"),
    ("inscription_registre", "Inscription / réinscription"),
    ("extrascolaire", "Prestations extrascolaires"),
    ("a_classer", "À classer"),
)


def fee_category_overrides(school):
    setting = SchoolSetting.objects.filter(school=school, scope_key=POLICY_SCOPE).only("values").first()
    values = setting.values if setting and isinstance(setting.values, dict) else {}
    records = values.get("assignments", {})
    valid = dict(PERMITTED_FEE_CATEGORIES)
    return {key: category for key, category in records.items()
            if isinstance(key, str) and isinstance(category, str)
            and category in valid} if isinstance(records, dict) else {}


def resolved_fee_category(schedule_id, code, frozen_label="", method="", *, overrides=None):
    """Demo always wins over any school mapping. All other fallbacks are legacy."""
    from .entry_income import _category
    original = _category(code, frozen_label, method)
    if original == "demo":
        return original
    return (overrides or {}).get(str(schedule_id), original)


def _response_error(message, status):
    return JsonResponse({"error": message}, status=status, headers={"Cache-Control": "no-store"})


@require_http_methods(["GET", "PATCH"])
@authorized
def fee_classifications(request, school_id):
    """GET a school's mappings; PATCH one schedule with revision and explicit audit.

    A recorded fee is not moved to another classification silently. The first
    classification of an existing legacy schedule requires an explicit audited
    acknowledgement, and cannot be changed again while charges exist.
    """
    permission = "school.finance.read" if request.method == "GET" else "school.finance.manage"
    school, error = gate(request, school_id, permission)
    if error is not None:
        return error

    if request.method == "GET":
        setting = SchoolSetting.objects.filter(school=school, scope_key=POLICY_SCOPE).first()
        return JsonResponse({
            "school": str(school.pk), "revision": setting.revision if setting else 0,
            "categories": [{"code": key, "label": label} for key, label in PERMITTED_FEE_CATEGORIES],
            "assignments": fee_category_overrides(school),
            "notes": "Les démonstrations restent exclues. Les tarifs historiques exigent une validation explicite.",
        }, headers={"Cache-Control": "no-store"})

    import json
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return _response_error("JSON invalide.", 400)
    if not isinstance(payload, dict) or set(payload) - {
        "schedule", "category", "revision", "reason", "acknowledge_history"
    }:
        return _response_error("Paramètres de classement invalides.", 422)
    key = payload.get("category")
    if not isinstance(key, str) or key not in dict(PERMITTED_FEE_CATEGORIES):
        return _response_error("Nature des frais non autorisée.", 422)
    version = payload.get("revision")
    if type(version) is not int or version < 0:
        return _response_error("Révision de classement invalide.", 422)
    reason = payload.get("reason")
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 240:
        return _response_error("Justification requise (10 à 240 caractères).", 422)
    try:
        schedule_id = UUID(str(payload.get("schedule")))
    except (ValueError, TypeError, AttributeError):
        return _response_error("Tarif introuvable.", 422)

    with transaction.atomic():
        # Serialize first-write creation (when SchoolSetting doesn't exist yet).
        School.objects.select_for_update().get(pk=school.pk)
        schedule = FeeSchedule.objects.filter(pk=schedule_id, school=school).first()
        if schedule is None:
            return _response_error("Tarif introuvable dans cet établissement.", 404)
        if schedule.code.lower().startswith("demo-"):
            return _response_error("Un tarif de démonstration ne peut pas devenir une recette réelle.", 422)
        setting = SchoolSetting.objects.select_for_update().filter(
            school=school, scope_key=POLICY_SCOPE,
        ).first()
        revision = setting.revision if setting else 0
        if revision != version:
            return JsonResponse({"error": "Le classement a été modifié ailleurs.", "revision": revision},
                                status=409, headers={"Cache-Control": "no-store"})
        existing = fee_category_overrides(school)
        old = existing.get(str(schedule.id))
        if old == key:
            return JsonResponse({"revision": revision, "category": key, "unchanged": True},
                                headers={"Cache-Control": "no-store"})
        has_charges = FeeCharge.objects.filter(school=school, schedule=schedule).exists()
        if has_charges and old is not None:
            return _response_error(
                "Ce classement est figé car des créances existent. Procédure comptable indépendante requise.", 409
            )
        if has_charges and payload.get("acknowledge_history") is not True:
            return _response_error(
                "Tarif historique : une confirmation explicite est requise avant son premier classement.", 422
            )
        existing[str(schedule.id)] = key
        if setting is None:
            setting = SchoolSetting(
                school=school, scope_key=POLICY_SCOPE,
                scope={"module": "income", "kind": "fee_classification"},
                revision=1,
            )
        else:
            setting.revision += 1
        setting.values = {"assignments": existing}
        setting.full_clean()
        setting.save()
        SchoolAudit.objects.create(
            school=school, actor=request.user, event="income_fee_classified",
            subject=str(schedule.id),
            details={"previous": old or "legacy_fallback", "category": key,
                     "reason": reason.strip(), "revision": setting.revision,
                     "historical_charges": has_charges},
        )
        return JsonResponse({
            "revision": setting.revision, "category": key, "unchanged": False,
            "historical_charges": has_charges,
        }, headers={"Cache-Control": "no-store"})
