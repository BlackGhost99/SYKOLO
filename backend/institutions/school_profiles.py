"""Catalogue des profils d'établissements YEM (Gabon).

La catégorie administrative est distincte des cycles effectivement ouverts.
Les profils sont des recommandations, pas des créations automatiques de classes
ou des autorisations accordées au personnel.
"""
CYCLE_LABELS = {
    "prescolaire": "Maternelle / préscolaire",
    "primaire": "Primaire",
    "college": "Collège / premier cycle secondaire",
    "lycee_general": "Lycée général / second cycle",
    "lycee_technique": "Lycée technique ou professionnel",
}

SCHOOL_PROFILES = {
    "maternelle": {
        "label": "Maternelle",
        "allowed_cycles": ("prescolaire",),
        "default_cycles": ("prescolaire",),
        "responsable": "Direction de la maternelle",
    },
    "primaire": {
        "label": "École primaire",
        "allowed_cycles": ("primaire",),
        "default_cycles": ("primaire",),
        "responsable": "Direction de l'école primaire",
    },
    "college": {
        "label": "Collège",
        "allowed_cycles": ("college",),
        "default_cycles": ("college",),
        "responsable": "Principal",
    },
    "lycee_general": {
        "label": "Lycée général",
        "allowed_cycles": ("college", "lycee_general"),
        "default_cycles": ("lycee_general",),
        "responsable": "Proviseur",
    },
    "lycee_technique": {
        "label": "Lycée technique ou professionnel",
        "allowed_cycles": ("college", "lycee_technique"),
        "default_cycles": ("lycee_technique",),
        "responsable": "Proviseur",
    },
    "groupe_scolaire": {
        "label": "Groupe scolaire / établissement mixte",
        "allowed_cycles": tuple(CYCLE_LABELS),
        "default_cycles": ("prescolaire", "primaire"),
        "responsable": "Direction générale",
    },
}

SCHOOL_TYPE_CHOICES = [("non_classe", "À classifier")] + [
    (code, profile["label"]) for code, profile in SCHOOL_PROFILES.items()
]


def profile_options():
    return [
        {
            "code": code,
            "label": profile["label"],
            "allowed_cycles": list(profile["allowed_cycles"]),
            "default_cycles": list(profile["default_cycles"]),
            "responsable": profile["responsable"],
        }
        for code, profile in SCHOOL_PROFILES.items()
    ]


def validate_school_profile(school_type, education_cycles):
    """Validate client input without silently dropping or inventing cycles."""
    profile = SCHOOL_PROFILES.get(school_type) if isinstance(school_type, str) else None
    if profile is None:
        raise ValueError("Catégorie d'établissement inconnue.")
    if not isinstance(education_cycles, list) or not education_cycles:
        raise ValueError("Sélectionnez au moins un cycle enseigné.")
    if any(not isinstance(cycle, str) for cycle in education_cycles):
        raise ValueError("Codes de cycles invalides.")
    if len(education_cycles) != len(set(education_cycles)):
        raise ValueError("Un cycle ne peut pas être choisi deux fois.")
    allowed = set(profile["allowed_cycles"])
    if any(cycle not in allowed for cycle in education_cycles):
        raise ValueError("Cycle incompatible avec la catégorie choisie.")
    return school_type, list(education_cycles)
