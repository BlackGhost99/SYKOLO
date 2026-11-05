"""Catalogue des fonctions administratives et pédagogiques de YEM.

Une fonction est une nomination organisationnelle (par établissement/cycle).
Elle ne confère AUCUNE permission API à elle seule : les droits restent contrôlés
par les rôles SchoolMember/SchoolRole, et toute délégation par cycle doit être
contrôlée dans les vues métier avant d'être rendue exécutoire.
"""
from .school_profiles import CYCLE_LABELS

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
    "censeur_principal": ("Censeur principal", "Pédagogie", "cycle", LYCEE, ()),
    "censeur_etudes": ("Censeur des études", "Pédagogie", "cycle", LYCEE, ()),
    "censeur_pedagogique": ("Censeur pédagogique", "Pédagogie", "cycle", LYCEE, ()),
    "responsable_pedagogique": ("Responsable pédagogique", "Pédagogie", "cycle", ALL_CYCLES, ()),
    "responsable_discipline": ("Responsable de discipline", "Pédagogie", "cycle", SECONDARY, ()),
    "professeur_principal": ("Professeur principal", "Pédagogie", "cycle", SECONDARY, ()),
    "instituteur": ("Instituteur / Enseignant du primaire", "Pédagogie", "cycle", ("primaire",), ()),
    "educateur_prescolaire": ("Éducateur / Enseignant préscolaire", "Pédagogie", "cycle", ("prescolaire",), ()),
    "enseignant": ("Enseignant", "Pédagogie", "cycle", ALL_CYCLES, ()),
    "censeur_vie_scolaire": ("Censeur de la vie scolaire", "Vie scolaire", "cycle", LYCEE, ()),
    "conseiller_education": ("Conseiller d'éducation", "Vie scolaire", "cycle", SECONDARY, ()),
    "surveillant_general": ("Surveillant général", "Vie scolaire", "cycle", SECONDARY, ()),
    "surveillant": ("Surveillant", "Vie scolaire", "cycle", ("primaire",) + SECONDARY, ()),
    "conseiller_orientation": ("Conseiller d'orientation", "Vie scolaire", "cycle", SECONDARY, ()),
    "chef_travaux": ("Chef de travaux", "Technique", "cycle", ("lycee_technique",), ()),
    "responsable_atelier": ("Responsable d'atelier", "Technique", "cycle", ("lycee_technique",), ()),
    "secretaire": ("Secrétaire administratif", "Administration", "school", ALL_CYCLES, ()),
    "intendant": ("Intendant", "Administration", "school", ALL_CYCLES, ()),
    "econome": ("Économe", "Administration", "school", ALL_CYCLES, ()),
    "comptable": ("Comptable", "Administration", "school", ALL_CYCLES, ()),
    "caissier": ("Caissier", "Administration", "school", ALL_CYCLES, ()),
    "assistant_scolaire": ("Assistant scolaire", "Administration", "cycle", ("prescolaire", "primaire"), ()),
}


def positions_for_school(school):
    """Return recommended functions only for cycles the school actually opens."""
    cycles = set(school.education_cycles or [])
    if school.school_type == "non_classe" or not cycles:
        return []
    positions = []
    for code, (label, family, scope, compatible, types) in FUNCTIONS.items():
        if types and school.school_type not in types:
            continue
        eligible = sorted(cycles.intersection(compatible))
        if scope == "cycle" and not eligible:
            continue
        positions.append({
            "code": code, "label": label, "family": family,
            "scope": scope, "allowed_cycles": eligible if scope == "cycle" else [],
        })
    return positions


def validate_position(school, code, cycle):
    position = next((p for p in positions_for_school(school) if p["code"] == code), None)
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
    return [p for p in options if p["code"] in school.enabled_functions]


def validate_account_functions(school, codes):
    if not isinstance(codes, list) or len(codes) > 40 or any(not isinstance(c, str) for c in codes):
        raise ValueError("Fonctions invalides.")
    if not set(codes) <= {p["code"] for p in account_functions(school)}:
        raise ValueError("Fonction non activée dans cet établissement.")
    return sorted(set(codes))
