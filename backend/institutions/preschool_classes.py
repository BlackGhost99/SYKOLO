"""Initialisation douce des classes maternelles : sans toucher aux dossiers existants.

Les niveaux sont permanents à l'établissement; les classes appartiennent à une
année scolaire. Une classe renommée compte comme déjà configurée pour son niveau.
"""
from django.db import transaction

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .school_profiles import CYCLE_LABELS

PRESCHOOL_DEFAULTS = (
    ("creche", "Crèche", "Crèche"),
    ("ps", "Petite section (3 ans)", "Petite section"),
    ("ms", "Moyenne section (4 ans)", "Moyenne section"),
    ("gs", "Grande section (5 ans)", "Grande section"),
)


def preschool_enabled(school):
    return "prescolaire" in (school.education_cycles or [])


def ensure_preschool_levels(school):
    """Installer le catalogue, sans écraser les intitulés personnalisés."""
    if not preschool_enabled(school):
        return []
    cycle, _ = AcademicCycle.objects.get_or_create(
        school=school, code="prescolaire",
        defaults={"name": CYCLE_LABELS["prescolaire"], "order": 1},
    )
    levels = []
    for order, (code, name, _) in enumerate(PRESCHOOL_DEFAULTS, start=1):
        level, _ = AcademicLevel.objects.get_or_create(
            school=school, cycle=cycle, code=code,
            defaults={"name": name, "order": order},
        )
        levels.append(level)
    return levels


def ensure_preschool_classes(school, year):
    """Créer une seule division par niveau absent, sans copier aucune donnée élève.

    L'appelant doit verrouiller l'établissement avant de lancer cette fonction.
    Réexécutable sans doublon. Une classe existante, même archivée ou renommée,
    ne doit jamais être remplacée.
    """
    if not preschool_enabled(school):
        return []
    if year.school_id != school.pk or not year.active or year.status == AcademicYear.STATUS_CLOSED:
        raise ValueError("L'année scolaire n'est pas modifiable.")
    levels = ensure_preschool_levels(school)
    existing = list(AcademicClass.objects.filter(school=school, year=year))
    represented = {room.level_id for room in existing}
    names = {room.name.casefold() for room in existing}
    codes = {room.code for room in existing}
    created = []
    for level, (code, _, short_label) in zip(levels, PRESCHOOL_DEFAULTS):
        if level.pk in represented:
            continue
        if not level.active or not level.cycle.active:
            continue
        for number in range(1, 501):
            suffix = chr(64 + number) if number <= 26 else str(number)
            name = f"{short_label} {suffix}"
            candidate = f"presc-{code}-{suffix.lower()}"
            if name.casefold() not in names and candidate not in codes:
                break
        else:
            raise ValueError("Impossible de proposer un nom unique pour la classe.")
        room = AcademicClass(
            school=school, year=year, level=level,
            code=candidate, name=name, active=True,
        )
        room.full_clean()
        room.save()
        created.append(room)
        names.add(name.casefold())
        codes.add(candidate)
    return created
