"""Fiche d'inscription modulable par établissement.

Le socle commun (nom, prénom, responsable principal) est toujours demandé. Le
secrétariat choisit quels champs facultatifs afficher ou rendre obligatoires,
ajoute ses propres questions et la liste des pièces à fournir.
"""
import copy
import json
import re
from datetime import date

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .overview_views import gate
from .student_models import EnrollmentFormConfig
from .views import parse_body, log_event

# Champs facultatifs du socle : (clé, libellé, section, visible par défaut, obligatoire par défaut)
BASE_FIELDS = [
    ("date_of_birth", "Date de naissance", "eleve", True, True),
    ("gender", "Sexe", "eleve", True, False),
    ("place_of_birth", "Lieu de naissance", "eleve", True, False),
    ("nationality", "Nationalité", "eleve", True, False),
    ("address", "Adresse / quartier", "eleve", True, False),
    ("previous_school", "Établissement précédent", "eleve", True, False),
    ("guardian_phone", "Téléphone du responsable", "responsable", True, True),
    ("guardian_email", "Email du responsable", "responsable", True, False),
    ("guardian_profession", "Profession du responsable", "responsable", True, False),
    ("guardian_address", "Adresse du responsable", "responsable", False, False),
    ("second_guardian", "Second responsable", "responsable", True, False),
]
BASE_KEYS = {k for k, *_ in BASE_FIELDS}
FIELD_TYPES = {"text", "textarea", "date", "number", "select", "yesno"}
SECTIONS = {"eleve", "responsable"}
DEFAULT_DOCUMENTS = [
    {"key": "acte_naissance", "label": "Acte de naissance", "required": True},
    {"key": "photos", "label": "2 photos d'identité", "required": True},
    {"key": "dernier_bulletin", "label": "Dernier bulletin", "required": False},
    {"key": "piece_responsable", "label": "Pièce d'identité du responsable", "required": False},
]
KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")


def default_config():
    return {
        "fields": {k: {"visible": v, "required": r} for k, _, _, v, r in BASE_FIELDS},
        "custom_fields": [],
        "documents": copy.deepcopy(DEFAULT_DOCUMENTS),
    }


def load_config(school):
    row = EnrollmentFormConfig.objects.filter(school=school).first()
    return (row.config if row else default_config()), (row.revision if row else 0)


def text(value, limit, what):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit or any(ord(c) < 32 for c in value):
        raise ValueError(f"{what} invalide ({limit} caractères au plus).")
    return value.strip()


def validate_config(raw):
    if not isinstance(raw, dict) or set(raw) - {"fields", "custom_fields", "documents"}:
        raise ValueError("Configuration invalide.")
    fields = {}
    for key, rule in (raw.get("fields") or {}).items():
        if key not in BASE_KEYS or not isinstance(rule, dict) or set(rule) - {"visible", "required"}:
            raise ValueError(f"Champ du socle inconnu : {key}.")
        visible, required = rule.get("visible", True), rule.get("required", False)
        if type(visible) is not bool or type(required) is not bool:
            raise ValueError("Options de champ invalides.")
        fields[key] = {"visible": visible, "required": required and visible}
    for key, _, _, v, r in BASE_FIELDS:
        fields.setdefault(key, {"visible": v, "required": r})
    fields["second_guardian"]["required"] = False
    custom, seen = [], set(BASE_KEYS)
    items = raw.get("custom_fields") or []
    if not isinstance(items, list) or len(items) > 30:
        raise ValueError("30 questions personnalisées au maximum.")
    for item in items:
        if not isinstance(item, dict) or set(item) - {"key", "label", "type", "options", "required", "section"}:
            raise ValueError("Question personnalisée invalide.")
        key = item.get("key")
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in seen:
            raise ValueError("Identifiant de question invalide ou en double.")
        seen.add(key)
        kind = item.get("type", "text")
        if kind not in FIELD_TYPES:
            raise ValueError("Type de question invalide.")
        options = []
        if kind == "select":
            options = item.get("options")
            if not isinstance(options, list) or not 1 <= len(options) <= 30:
                raise ValueError("Une liste de choix doit contenir entre 1 et 30 options.")
            options = list(dict.fromkeys(text(o, 120, "Option") for o in options))
        if type(item.get("required", False)) is not bool or item.get("section", "eleve") not in SECTIONS:
            raise ValueError("Options de question invalides.")
        custom.append({"key": key, "label": text(item.get("label"), 120, "Libellé"), "type": kind, "options": options,
                       "required": item.get("required", False), "section": item.get("section", "eleve")})
    docs, seen_docs = [], set()
    items = raw.get("documents") or []
    if not isinstance(items, list) or len(items) > 30:
        raise ValueError("30 pièces au maximum.")
    for item in items:
        if not isinstance(item, dict) or set(item) - {"key", "label", "required"}:
            raise ValueError("Pièce à fournir invalide.")
        key = item.get("key")
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in seen_docs:
            raise ValueError("Identifiant de pièce invalide ou en double.")
        seen_docs.add(key)
        if type(item.get("required", False)) is not bool:
            raise ValueError("Options de pièce invalides.")
        docs.append({"key": key, "label": text(item.get("label"), 120, "Libellé"), "required": item.get("required", False)})
    return {"fields": fields, "custom_fields": custom, "documents": docs}


def clean_answers(config, extra_fields, documents, *, partial=False):
    """Valide les réponses aux questions de l'école et les pièces cochées.

    `partial=True` (modification d'une fiche existante) n'exige pas les questions obligatoires absentes.
    Les réponses à des questions supprimées depuis sont conservées telles quelles.
    """
    extra_fields = extra_fields if extra_fields is not None else {}
    documents = documents if documents is not None else {}
    if not isinstance(extra_fields, dict) or not isinstance(documents, dict):
        raise ValueError("Réponses invalides.")
    if len(json.dumps(extra_fields, ensure_ascii=False)) > 8000:
        raise ValueError("Réponses trop volumineuses.")
    questions = {q["key"]: q for q in config.get("custom_fields", [])}
    clean = {}
    for key, value in extra_fields.items():
        q = questions.get(key)
        if q is None:
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                raise ValueError("Réponse invalide.")
            clean[key] = value
            continue
        if value in ("", None):
            continue
        kind = q["type"]
        if kind in ("text", "textarea"):
            value = text(value, 1000 if kind == "textarea" else 255, q["label"])
        elif kind == "date":
            try:
                if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError:
                raise ValueError(f"Date invalide pour « {q['label']} ».") from None
        elif kind == "number":
            if type(value) not in (int, float) or not -1e9 < value < 1e9:
                raise ValueError(f"Nombre invalide pour « {q['label']} ».")
        elif kind == "select":
            if value not in q["options"]:
                raise ValueError(f"Choix invalide pour « {q['label']} ».")
        elif kind == "yesno" and type(value) is not bool:
            raise ValueError(f"Réponse oui/non attendue pour « {q['label']} ».")
        clean[key] = value
    if not partial:
        missing = [q["label"] for q in questions.values() if q["required"] and q["type"] != "yesno" and clean.get(q["key"]) in (None, "")]
        if missing:
            raise ValueError("Champs obligatoires manquants : " + ", ".join(missing))
    known = {d["key"] for d in config.get("documents", [])}
    docs = {}
    for key, value in documents.items():
        if type(value) is not bool or (key not in known and not KEY.fullmatch(str(key))):
            raise ValueError("Pièce fournie invalide.")
        docs[key] = value
    return clean, docs


def missing_documents(config, documents):
    return [d["label"] for d in config.get("documents", []) if d["required"] and not (documents or {}).get(d["key"])]


def check_base(config, student, guardian):
    """Champs du socle rendus obligatoires par l'établissement."""
    labels = {k: label for k, label, *_ in BASE_FIELDS}
    rules = config.get("fields", {})
    missing = []
    for key, rule in rules.items():
        if not rule.get("required") or not rule.get("visible", True) or key == "second_guardian":
            continue
        source, name = (guardian or {}, key[len("guardian_"):]) if key.startswith("guardian_") else (student, key)
        if not str(source.get(name) or "").strip():
            missing.append(labels.get(key, key))
    if missing:
        raise ValueError("Champs obligatoires manquants : " + ", ".join(missing))


@require_http_methods(["GET", "PUT"])
@authorized
def enrollment_form(request, school_id):
    school, error = gate(request, school_id, "school.students.read" if request.method == "GET" else "school.students.manage")
    if error is not None:
        return error
    if request.method == "GET":
        config, revision = load_config(school)
        return JsonResponse({"config": config, "revision": revision,
                             "base_fields": [{"key": k, "label": label, "section": s} for k, label, s, *_ in BASE_FIELDS],
                             "field_types": sorted(FIELD_TYPES)})
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) != {"config", "revision"} or type(data["revision"]) is not int:
        return JsonResponse({"error": "Configuration et révision requises."}, status=422)
    try:
        config = validate_config(data["config"])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    with transaction.atomic():
        row = EnrollmentFormConfig.objects.select_for_update().filter(school=school).first()
        current = row.revision if row else 0
        if current != data["revision"]:
            return JsonResponse({"error": "La fiche a été modifiée entre-temps : rechargez la page.", "revision": current}, status=409)
        if row is None:
            row = EnrollmentFormConfig.objects.create(school=school, config=config, revision=1)
        else:
            row.config = config
            row.revision += 1
            row.save()
        log_event(school, request, "enrollment_form_updated", school.pk)
    return JsonResponse({"config": row.config, "revision": row.revision})
