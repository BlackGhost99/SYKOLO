"""School-scoped and year/level-scoped admission policies.

No automatic national examination result verification is claimed. Evidence is
attested by an authorized human reviewer in the school, with an audit trail.
"""
import re
from .admission_models import AdmissionPolicy, AdmissionDocument

ROUTES = ("direct", "concours", "orientation")
PROOF_CODES = {"direct": (), "concours": ("concours_result",),
               "orientation": ("orientation_decision",)}
DOCUMENT_CODE = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
DEFAULT_DOCUMENTS = {route: [] for route in ROUTES}


def policy_key(year_id, level_id=None):
    return f"{year_id}:{level_id or 'all'}"


def effective_policy(school, year, level):
    return (AdmissionPolicy.objects.filter(school=school, year=year, level=level).first()
            or AdmissionPolicy.objects.filter(school=school, year=year, level__isnull=True).first())


def policy_view(school, year, level, row=None):
    return {
        "year": str(year.pk), "level": str(level.pk) if level else None,
        "scope": "level" if row and row.level_id else ("year" if row else "default"),
        "enabled_routes": row.enabled_routes if row else list(ROUTES),
        "required_documents": row.required_documents if row else DEFAULT_DOCUMENTS,
        "revision": row.revision if row else 0,
    }


def validate_policy(payload):
    enabled = payload.get("enabled_routes")
    documents = payload.get("required_documents")
    if (not isinstance(enabled, list) or not enabled or len(enabled) > len(ROUTES)
            or any(not isinstance(x, str) or x not in ROUTES for x in enabled)
            or len(set(enabled)) != len(enabled)):
        raise ValueError("Sélection des voies d'admission invalide.")
    if not isinstance(documents, dict) or set(documents) - set(ROUTES):
        raise ValueError("Configuration des documents invalide.")
    clean = {}
    for route in ROUTES:
        codes = documents.get(route, [])
        if (not isinstance(codes, list) or len(codes) > 30
                or any(not isinstance(code, str) or not DOCUMENT_CODE.fullmatch(code) for code in codes)
                or len(set(codes)) != len(codes)):
            raise ValueError("Liste de pièces justificatives invalide.")
        clean[route] = codes
    return enabled, clean


def required_for_route(route, policy=None):
    if route not in ROUTES:
        raise ValueError("Voie d'admission inconnue.")
    configured = (policy.required_documents if policy else DEFAULT_DOCUMENTS).get(route, [])
    return list(dict.fromkeys([*PROOF_CODES[route], *configured]))


def missing_verified(application):
    required = application.required_documents or []
    if not required:
        # Existing historical applications remain compatible (direct route).
        required = list(PROOF_CODES[application.route])
    checked = set(AdmissionDocument.objects.filter(application=application, school=application.school,
                                                    status="verified", code__in=required)
                  .values_list("code", flat=True))
    return [code for code in required if code not in checked]


def admission_blocker(application):
    if application.route in ("concours", "orientation"):
        if application.external_result != "eligible":
            return "Le concours ou l'affectation n'est pas confirmé comme éligible."
        if not application.route_reference:
            return "Une référence officielle ou de concours est nécessaire."
        if application.route == "orientation" and not application.orientation_authority:
            return "L'autorité d'affectation doit être renseignée."
    absent = missing_verified(application)
    if absent:
        return "Pièces justificatives à vérifier : " + ", ".join(absent)
    return None
