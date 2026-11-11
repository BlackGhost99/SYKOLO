"""Catalogue des fonctions administratives et pédagogiques de YEM.

Une fonction est une nomination organisationnelle (par établissement/cycle).
Elle ne confère AUCUNE permission API à elle seule : les droits restent contrôlés
par les rôles SchoolMember/SchoolRole, et toute délégation par cycle doit être
contrôlée dans les vues métier avant d'être rendue exécutoire.
"""
from .school_profiles import CYCLE_LABELS
from .school_governance import GOVERNANCE_FUNCTIONS, governance_position_codes

ALL_CYCLES = tuple(CYCLE_LABELS)
SECONDARY = ("college", "lycee_general", "lycee_technique")
LYCEE = ("lycee_general", "lycee_technique")

FUNCTIONS = {
    "direction_generale": ("Direction générale", "Direction", "school", ALL_CYCLES, ("groupe_scolaire",)),
    "direction_etablissement": ("Chef d'établissement", "Direction", "school", ALL_CYCLES, ()),
    "directeur_maternelle": ("Directeur / Directrice de maternelle", "Direction", "cycle", ("prescolaire",), ()),
    "directeur_primaire": ("Directeur / Directrice du primaire", "Direction", "cycle", ("primaire",), ()),
    "principal": ("Principal du collège", "Direction", "cycle", ("college",), ()),
    "proviseur": ("Proviseur du lycée", "Direction", "cycle", LYCEE, ()),
    "directeur_etudes": ("Directeur des études", "Pédagogie", "cycle", SECONDARY, ()),
    "charge_etudes": ("Chargé / Chargée des études", "Pédagogie", "cycle", SECONDARY, ()),
    "censeur_principal": ("Censeur principal", "Pédagogie", "cycle", LYCEE, ()),
    "censeur_etudes": ("Censeur des études", "Pédagogie", "cycle", LYCEE, ()),
    "censeur_pedagogique": ("Censeur pédagogique", "Pédagogie", "cycle", LYCEE, ()),
    "responsable_pedagogique": ("Responsable pédagogique", "Pédagogie", "cycle", ALL_CYCLES, ()),
    "responsable_discipline": ("Responsable de discipline", "Pédagogie", "cycle", SECONDARY, ()),
    "professeur_principal": ("Professeur principal", "Pédagogie", "cycle", SECONDARY, ()),
    "instituteur": ("Instituteur / Enseignant du primaire", "Pédagogie", "cycle", ("primaire",), ()),
    "educateur_prescolaire": ("Éducateur / Éducatrice de maternelle", "Pédagogie", "cycle", ("prescolaire",), ()),
    "enseignant": ("Enseignant", "Pédagogie", "cycle", ALL_CYCLES, ()),
    "censeur_vie_scolaire": ("Censeur de la vie scolaire", "Vie scolaire", "cycle", LYCEE, ()),
    "directeur_vie_scolaire": ("Directeur / Directrice de la vie scolaire", "Vie scolaire", "cycle", SECONDARY, ()),
    "conseiller_education": ("Conseiller d'éducation", "Vie scolaire", "cycle", SECONDARY, ()),
    "surveillant_general": ("Surveillant général", "Vie scolaire", "cycle", SECONDARY, ()),
    "surveillant_general_adjoint": ("Surveillant général adjoint", "Vie scolaire", "cycle", SECONDARY, ()),
    "surveillant": ("Surveillant", "Vie scolaire", "cycle", ("primaire",) + SECONDARY, ()),
    "conseiller_orientation": ("Conseiller d'orientation", "Vie scolaire", "cycle", SECONDARY, ()),
    "chef_travaux": ("Chef de travaux", "Technique", "cycle", ("lycee_technique",), ()),
    "responsable_formation_continue": ("Direction des études · formation continue", "Technique", "cycle", ("lycee_technique",), ()),
    "responsable_atelier": ("Responsable d'atelier", "Technique", "cycle", ("lycee_technique",), ()),
    "secretaire": ("Secrétaire administratif", "Administration", "school", ALL_CYCLES, ()),
    "secretaire_pedagogique": ("Secrétaire pédagogique", "Administration", "cycle", SECONDARY, ()),
    "intendant": ("Intendant", "Administration", "school", ALL_CYCLES, ()),
    "econome": ("Économe", "Administration", "school", ALL_CYCLES, ()),
    "comptable": ("Comptable", "Administration", "school", ALL_CYCLES, ()),
    "caissier": ("Caissier", "Administration", "school", ALL_CYCLES, ()),
    "assistant_scolaire": ("Assistant scolaire", "Administration", "cycle", ("prescolaire", "primaire"), ()),
    "directeur_etudes_formation_initiale": ("Directeur des études · formation initiale", "Technique", "cycle", ("lycee_technique",), ()),
    "directeur_etudes_vie_scolaire": ("Directeur des études · vie scolaire", "Vie scolaire", "cycle", ("lycee_technique",), ()),
    "chef_departement": ("Chef de département pédagogique ou technique", "Technique", "cycle", ("lycee_technique",), ()),
    "responsable_stages": ("Responsable des stages et relations entreprises", "Technique", "cycle", ("lycee_technique",), ()),
    "assistant_social": ("Assistant social scolaire", "Vie scolaire", "cycle", SECONDARY, ()),
    "psychologue_orientation": ("Psychologue de l’orientation", "Vie scolaire", "cycle", SECONDARY, ()),
    **{code: (label, family, "school", ALL_CYCLES, ())
       for rows in GOVERNANCE_FUNCTIONS.values() for code, label, family in rows},
}


# Les anciens codes restent lisibles et sont regroupés lors de la saisie.
FUNCTION_ALIASES = {
    "college": {"direction_etablissement": "principal"},
    "lycee_general": {"direction_etablissement": "proviseur"},
    "lycee_technique": {"direction_etablissement": "proviseur"},
    "maternelle": {
        "direction_etablissement": "directeur_maternelle",
        "enseignant": "educateur_prescolaire",
        "econome": "caissier",
    },
    "primaire": {
        "direction_etablissement": "directeur_primaire",
        "enseignant": "instituteur",
        "econome": "caissier",
    },
}
SECONDARY_COMMON_POSITIONS = (
    "charge_etudes", "directeur_vie_scolaire", "secretaire_pedagogique",
    "enseignant", "professeur_principal", "responsable_pedagogique",
    "responsable_discipline", "surveillant_general", "surveillant_general_adjoint",
    "conseiller_education", "surveillant", "conseiller_orientation",
    "secretaire", "intendant", "comptable", "econome", "caissier",
)
LYCEE_POSITIONS = (
    "proviseur", "principal", "directeur_etudes", "censeur_principal",
    "censeur_pedagogique", "censeur_etudes", "censeur_vie_scolaire",
)

PROFILE_POSITIONS = {
    "college": ("principal", "directeur_etudes", *SECONDARY_COMMON_POSITIONS),
    "lycee_general": (*LYCEE_POSITIONS, *SECONDARY_COMMON_POSITIONS),
    "lycee_technique": (
        *LYCEE_POSITIONS, "responsable_formation_continue", "chef_travaux", "responsable_atelier",
        *SECONDARY_COMMON_POSITIONS,
    ),
    "maternelle": (
        "directeur_maternelle", "secretaire", "educateur_prescolaire",
        "assistant_scolaire", "responsable_pedagogique", "comptable", "caissier", "intendant",
    ),
    "primaire": (
        "directeur_primaire", "secretaire", "instituteur", "responsable_pedagogique",
        "assistant_scolaire", "surveillant", "comptable", "caissier", "intendant",
    ),
}
PROFILE_FUNCTION_LABELS = {
    "lycee_technique": {"censeur_vie_scolaire": "Direction de la vie scolaire / Censeur"},
    "maternelle": {"caissier": "Caisse / Économat"},
    "primaire": {
        "directeur_primaire": "Direction du primaire",
        "instituteur": "Enseignant / Enseignante du primaire",
        "secretaire": "Secrétariat du primaire",
        "surveillant": "Vie scolaire / Surveillance",
        "caissier": "Caisse / Économat",
    },
}


def function_aliases(school):
    return FUNCTION_ALIASES.get(school.school_type, {})


def account_function_codes(school, codes):
    aliases = function_aliases(school)
    return sorted({aliases.get(code, code) for code in codes})


def function_label(school, code):
    canonical = account_function_codes(school, [code])[0]
    labels = PROFILE_FUNCTION_LABELS.get(school.school_type, {})
    return labels.get(canonical, FUNCTIONS.get(canonical, (canonical,))[0])


def positions_for_school(school):
    """Return recommended functions only for cycles the school actually opens."""
    cycles = set(school.education_cycles or [])
    if school.school_type == "non_classe" or not cycles:
        return []
    positions = []
    codes = list(PROFILE_POSITIONS.get(school.school_type, FUNCTIONS))
    if "lycee_technique" in cycles:
        codes.extend(("directeur_etudes_formation_initiale", "directeur_etudes_vie_scolaire",
                      "chef_departement", "responsable_stages"))
    if cycles.intersection(SECONDARY):
        codes.extend(("assistant_social", "psychologue_orientation"))
    permitted_governance = set(governance_position_codes(school))
    governance_all = {code for rows in GOVERNANCE_FUNCTIONS.values() for code, _, _ in rows}
    codes.extend(permitted_governance)
    for code in dict.fromkeys(codes):
        if code in governance_all and code not in permitted_governance:
            continue
        _, family, scope, compatible, types = FUNCTIONS[code]
        if types and school.school_type not in types:
            continue
        eligible = sorted(cycles.intersection(compatible))
        if scope == "cycle" and not eligible:
            continue
        positions.append({
            "code": code, "label": function_label(school, code), "family": family,
            "scope": scope, "allowed_cycles": eligible if scope == "cycle" else [],
        })
    return positions


def validate_position(school, code, cycle):
    position = next((p for p in positions_for_school(school) if p["code"] == code), None)
    if position is None and code in function_aliases(school):
        # Les nominations existantes gardent leur périmètre et restent modifiables.
        _, _, scope, compatible, _ = FUNCTIONS[code]
        position = {"scope": scope, "allowed_cycles": set(compatible).intersection(school.education_cycles)}
    if position is None:
        raise ValueError("Fonction non disponible pour les cycles de cet établissement.")
    if position["scope"] == "school":
        if cycle:
            raise ValueError("Cette fonction concerne l'établissement entier.")
    elif cycle not in position["allowed_cycles"]:
        raise ValueError("Choisissez un cycle enseigné compatible avec cette fonction.")
    return position


def account_functions(school):
    options = positions_for_school(school)
    if school.enabled_functions is None:
        return options
    enabled = account_function_codes(school, school.enabled_functions)
    return [p for p in options if p["code"] in enabled]


def suggested_account_function(school, role_code, options):
    aliases = function_aliases(school)
    code = {
        "direction": aliases.get("direction_etablissement", "direction_generale"),
        "principal": "principal", "proviseur": "proviseur",
        "enseignant": aliases.get("enseignant", "enseignant"),
        "secretariat": "secretaire", "econome": "caissier", "comptabilite": "comptable",
        "secretariat_pedagogique": "secretaire_pedagogique",
        "etudes": "censeur_pedagogique" if school.school_type == "lycee_general" else "directeur_etudes",
        "vie_scolaire": "surveillant_general" if school.school_type == "college" else "censeur_vie_scolaire",
        "censeur_principal": "censeur_principal", "surveillance_generale": "surveillant_general",
        "surveillance": "surveillant", "chef_travaux": "chef_travaux",
    }.get(role_code, "")
    return code if any(option["code"] == code for option in options) else ""


def validate_account_functions(school, codes):
    if not isinstance(codes, list) or len(codes) > 40 or any(not isinstance(c, str) for c in codes):
        raise ValueError("Fonctions invalides.")
    codes = account_function_codes(school, codes)
    if not set(codes) <= {p["code"] for p in account_functions(school)}:
        raise ValueError("Fonction non activée dans cet établissement.")
    return sorted(set(codes))
