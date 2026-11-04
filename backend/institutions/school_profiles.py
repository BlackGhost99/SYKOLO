"""Configurable Gabon school profiles; do not infer a school's cycle from its name.

The profile is descriptive. Existing academic cycles/levels and historical
permissions remain unchanged until explicitly configured by the school.
"""
from django.core.exceptions import ValidationError

SCHOOL_TYPES = (
    ("a_configurer", "Type à configurer"),
    ("maternelle", "Maternelle"),
    ("primaire", "École primaire"),
    ("college", "Collège"),
    ("lycee", "Lycée"),
    ("groupe_scolaire", "Groupe scolaire / multicyle"),
)
CYCLE_TYPES = (
    ("maternelle", "Pré-primaire / maternelle"),
    ("primaire", "Primaire"),
    ("college", "Secondaire : collège"),
    ("lycee", "Secondaire : lycée"),
)
TYPE_CYCLES = {
    "a_configurer": (),
    "maternelle": ("maternelle",),
    "primaire": ("primaire",),
    "college": ("college",),
    "lycee": ("lycee",),
}
CYCLE_CODES = {code for code, _ in CYCLE_TYPES}
SCHOOL_CODES = {code for code, _ in SCHOOL_TYPES}

# These are suggested workflows, not substitutes for backend role checks.
CYCLE_WORKFLOWS = {
    "maternelle": ("eveil", "bilan_developpement", "garderie", "cantine"),
    "primaire": ("evaluations", "bulletins", "cep", "suivi_classe"),
    "college": ("evaluations", "bulletins", "emplois_du_temps", "vie_scolaire", "conseils", "bepc"),
    "lycee": ("evaluations", "bulletins", "emplois_du_temps", "vie_scolaire", "conseils", "bac", "filieres"),
}
TYPE_DIRECTOR_LABEL = {
    "maternelle": "Direction maternelle",
    "primaire": "Direction primaire",
    "college": "Direction / Principal",
    "lycee": "Direction / Proviseur",
    "groupe_scolaire": "Direction générale",
}


def validate_profile(school_type, enabled_cycles):
    """Return normalized profile or raise, never silently choose a cycle."""
    if school_type not in SCHOOL_CODES:
        raise ValidationError({"school_type": "Type d'établissement inconnu."})
    if not isinstance(enabled_cycles, list):
        raise ValidationError({"enabled_cycles": "Liste de cycles requise."})
    if len(enabled_cycles) != len(set(str(x) for x in enabled_cycles)):
        raise ValidationError({"enabled_cycles": "Un cycle ne doit apparaître qu'une fois."})
    if any(not isinstance(x, str) or x not in CYCLE_CODES for x in enabled_cycles):
        raise ValidationError({"enabled_cycles": "Cycle d'enseignement inconnu."})
    if school_type == "groupe_scolaire":
        if not enabled_cycles:
            raise ValidationError({"enabled_cycles": "Indiquer au moins un cycle pour le groupe scolaire."})
    elif set(enabled_cycles) != set(TYPE_CYCLES[school_type]):
        raise ValidationError({"enabled_cycles": "Cycles incompatibles avec le type d'établissement."})
    return school_type, sorted(enabled_cycles, key=lambda c: list(CYCLE_CODES_ORDER).index(c))


CYCLE_CODES_ORDER = ("maternelle", "primaire", "college", "lycee")


def profile_fields(data, current_type="a_configurer", current_cycles=None):
    """Validate supplied API values; omitted type preserves the current profile."""
    if not isinstance(data, dict):
        raise ValidationError("Configuration invalide.")
    school_type = data.get("school_type", current_type)
    cycles = data.get("enabled_cycles")
    if cycles is None and "enabled_cycles" in data:
        raise ValidationError({"enabled_cycles": "Liste de cycles requise."})
    if cycles is None:
        cycles = list(current_cycles or []) if school_type == current_type else list(TYPE_CYCLES.get(school_type, ()))
    return validate_profile(school_type, cycles)


def profile_payload(school):
    types = dict(SCHOOL_TYPES)
    workflows = sorted({w for cycle in school.enabled_cycles for w in CYCLE_WORKFLOWS.get(cycle, ())})
    return {
        "school_type": school.school_type,
        "school_type_label": types.get(school.school_type, types["a_configurer"]),
        "enabled_cycles": school.enabled_cycles,
        "profile_revision": school.profile_revision,
        "recommended_workflows": workflows,
    }
