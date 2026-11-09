"""Suggestions de séries pour les lycées au Gabon, jamais des classes ouvertes.

L'annuaire statistique gabonais 2020/21 décrit :
seconde LE/S, première A1/A2/B/S, terminale A1/A2/B/C/D.
https://instatgabon.org/uploads/folder_1/RGOE/Annuaire_2020-2021_31_10_2023_.pdf

La plateforme BacTech liste des séries de baccalauréat technique (non une
liste réglementaire exhaustive des intitulés de chaque classe par niveau) :
https://bactechgabon.com/affiche_listinscritserie.php

Les établissements ne sont jamais présumés enseigner toutes ces séries ;
aucune classe ne doit être publiée par simple présence dans le catalogue.
"""
from django.utils.text import slugify

from .school_profiles import CYCLE_LABELS

GENERAL_SERIES = {
    "seconde": (("LE", "Littéraire (LE)"), ("S", "Scientifique (S)")),
    "premiere": (
        ("A1", "Lettres A1"), ("A2", "Lettres A2"),
        ("B", "Sciences économiques et sociales (B)"), ("S", "Scientifique (S)"),
    ),
    "terminale": (
        ("A1", "Lettres A1"), ("A2", "Lettres A2"), ("B", "Sciences économiques et sociales (B)"),
        ("C", "Mathématiques et sciences physiques (C)"), ("D", "Sciences de la vie (D)"),
    ),
}

# Propositions issues des examens technologiques : disponibilité à vérifier
# par l'établissement, et répartition par niveau propre à chaque lycée.
TECHNICAL_SERIES = (
    ("ACA", "Action et communication administratives"),
    ("ACC", "Action et communication commerciales"),
    ("ACG", "Administration / comptabilité / gestion (nom local à confirmer)"),
    ("CG", "Comptabilité et gestion"),
    ("CFE", "Comptabilité et finance d'entreprise"),
    ("F1", "Génie mécanique"), ("F1C", "Structures métalliques"),
    ("F1D", "Bois et matériaux associés"),
    ("F2", "Génie électronique"), ("F3", "Génie électrotechnique"),
    ("F4", "Génie civil"), ("MI", "Maintenance industrielle"),
    ("MSI", "Maintenance des systèmes industriels"),
    ("SI", "Sciences de l'ingénieur"), ("GSI", "Gestion des systèmes d'information"),
    ("RHC", "Ressources humaines et communication"),
    ("M", "Mercatique"), ("ERE", "Énergies renouvelables et environnement"),
    ("BIOT", "Biotechnologie"), ("SPCL", "Sciences physiques et chimie de laboratoire"),
)

SECONDARY_CYCLES = frozenset(("lycee_general", "lycee_technique"))
SECONDARY_LEVELS = frozenset(("seconde", "premiere", "terminale"))


def series_for_level(cycle_code, level_code):
    if cycle_code == "lycee_general":
        options = GENERAL_SERIES.get(level_code, ())
        return [{"code": code, "name": label, "kind": "referenced"} for code, label in options]
    if cycle_code == "lycee_technique" and level_code in SECONDARY_LEVELS:
        return [{"code": code, "name": label, "kind": "suggestion"}
                for code, label in TECHNICAL_SERIES]
    return []


def series_slug(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 40:
        raise ValueError("Série invalide (1 à 40 caractères).")
    code = slugify(value.strip())
    if not code or len(code) > 40 or not code[0].isalnum():
        raise ValueError("Code de série invalide.")
    return code


def series_display_name(code, cycle, level):
    return next((item["name"] for item in series_for_level(cycle, level)
                 if item["code"].casefold() == code.casefold()), code)
