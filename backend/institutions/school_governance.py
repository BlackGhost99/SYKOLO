"""Profils de gouvernance des établissements gabonais.

Régime juridique ≠ type de cycles ≠ poste ≠ permission. Ces modèles donnent
des recommandations de paramétrage, jamais une autorisation ministérielle.
"""
GOVERNANCE_MODES = {
    "public": {
        "label": "Public",
        "sector": "public",
        "authority": "Tutelle publique / autorités compétentes",
        "description": "Direction nommée et tutelle de l'État ; organes collégiaux distincts de la direction.",
    },
    "prive_laique": {
        "label": "Privé laïc",
        "sector": "prive",
        "authority": "Fondateur / promoteur ou organe gestionnaire",
        "description": "Gouvernance privée avec contrôle et autorisations des autorités éducatives.",
    },
    "prive_confessionnel": {
        "label": "Privé confessionnel",
        "sector": "prive",
        "authority": "Organisme fondateur / autorité de tutelle confessionnelle",
        "description": "Gouvernance privée et autorité confessionnelle ; respect des programmes officiels.",
    },
}
DEFAULT_GOVERNANCE_MODE = "prive_laique"
GOVERNANCE_CHOICES = [
    (code, entry["label"]) for code, entry in GOVERNANCE_MODES.items()
]

# Fonctions indicatives : elles ne déclenchent pas l'octroi de permissions.
GOVERNANCE_FUNCTIONS = {
    "public": (
        ("referent_relation_tutelle", "Référent administratif auprès de la tutelle", "Administration"),
        ("gestionnaire_credit_public", "Gestionnaire des crédits publics", "Administration"),
    ),
    "prive_laique": (
        ("responsable_administratif_prive", "Responsable administratif de l’établissement", "Administration"),
    ),
    "prive_confessionnel": (
        ("referent_confessionnel_interne", "Référent interne auprès de l’organisme confessionnel", "Administration"),
        ("responsable_pastorale", "Responsable de la pastorale / aumônier", "Vie scolaire"),
        ("responsable_administratif_prive", "Responsable administratif de l’établissement", "Administration"),
    ),
}

# Presets facultatifs, sans pouvoir de paiement, sanction, création de rôles ou validation.
# Les droits opérationnels réels continuent de passer par SchoolRole et les contrôles API.
GOVERNANCE_ROLE_TEMPLATES = {
    "public": (
        ("tutelle_consultation", "Tutelle publique — consultation", ("school.view", "school.academic.read")),
        ("presidence_conseil", "Présidence du conseil — consultation", ("school.view",)),
    ),
    "prive_laique": (
        ("responsable_gestionnaire", "Organisme gestionnaire — consultation", ("school.view",)),
    ),
    "prive_confessionnel": (
        ("responsable_gestionnaire", "Organisme gestionnaire — consultation", ("school.view",)),
        ("referent_confessionnel", "Référent confessionnel — consultation", ("school.view",)),
    ),
}

# Organes de référence : une décision de conseil n'est pas équivalente à
# une autorisation individuelle d'exécuter une dépense ou de modifier un bulletin.
BASE_ORGANS = (
    "Conseil d'administration ou instance de gouvernance applicable",
    "Conseil d'établissement",
    "Conseil d'enseignement",
    "Conseil de classe",
    "Conseil de discipline",
)
SECONDARY_ORGANS = ("Conseil d'orientation",)
TECHNICAL_ORGANS = ("Conseil de perfectionnement", "Comité d'hygiène et de sécurité")


def validate_governance_mode(code):
    if not isinstance(code, str) or code not in GOVERNANCE_MODES:
        raise ValueError("Choisissez une gouvernance publique, privée laïque ou privée confessionnelle.")
    return code


def governance_mode_for(school):
    return getattr(school, "governance_mode", DEFAULT_GOVERNANCE_MODE)


def governance_profile(school):
    code = governance_mode_for(school)
    if code not in GOVERNANCE_MODES:
        code = DEFAULT_GOVERNANCE_MODE
    info = GOVERNANCE_MODES[code]
    cycles = set(school.education_cycles or [])
    organs = list(BASE_ORGANS)
    if cycles & {"college", "lycee_general", "lycee_technique"}:
        organs.extend(SECONDARY_ORGANS)
    if "lycee_technique" in cycles:
        organs.extend(TECHNICAL_ORGANS)
    return {
        "mode": code,
        "label": info["label"],
        "sector": info["sector"],
        "authority": info["authority"],
        "description": info["description"],
        "organs": organs,
        "notice": "Référentiel indicatif : une fonction, un siège au conseil et un rôle applicatif sont distincts.",
    }


def governance_options():
    return [
        {"code": code, **info}
        for code, info in GOVERNANCE_MODES.items()
    ]


def governance_role_templates(school):
    return list(GOVERNANCE_ROLE_TEMPLATES[governance_mode_for(school)])


def governance_position_codes(school):
    return [row[0] for row in GOVERNANCE_FUNCTIONS[governance_mode_for(school)]]
