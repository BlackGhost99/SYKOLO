"""Compatibilité des fonctions de préconfiguration préscolaire existantes.

L'initialisation des autres cycles passe par standard_classes.py ; les
anciens appels maternels conservent exactement leurs signatures.
"""
from .standard_classes import ensure_standard_levels, ensure_standard_classes

PRESCHOOL_DEFAULTS = (
    ("creche", "Crèche", "Crèche"),
    ("ps", "Petite section (3 ans)", "Petite section"),
    ("ms", "Moyenne section (4 ans)", "Moyenne section"),
    ("gs", "Grande section (5 ans)", "Grande section"),
)


def preschool_enabled(school):
    return "prescolaire" in (school.education_cycles or [])


def ensure_preschool_levels(school):
    return [level for level, _ in ensure_standard_levels(
        school, cycles=("prescolaire",)
    ).get("prescolaire", [])]


def ensure_preschool_classes(school, year):
    return ensure_standard_classes(school, year, cycles=("prescolaire",))
