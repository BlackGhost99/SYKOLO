"""Préconfiguration non destructive des niveaux et classes scolaires YEM.

Le niveau appartient à l'établissement. Une classe (division) appartient à
une année, et son nom peut être librement adapté par l'établissement.
Aucune matière, filière, donnée d'élève ou facturation n'est créée ici.
"""
from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .school_profiles import CLASS_LEVELS, CYCLE_LABELS


def enabled_standard_cycles(school, cycles=None):
    configured = [code for code in (school.education_cycles or []) if code in CLASS_LEVELS]
    if cycles is None:
        return configured
    requested = list(cycles)
    if len(set(requested)) != len(requested) or any(code not in configured for code in requested):
        raise ValueError("Cycle non ouvert dans cet établissement.")
    return [code for code in configured if code in requested]


def default_class_base(cycle_code, level_name):
    """Noms d'accueil, sans confondre séries scolaires et divisions A/B."""
    if cycle_code == "prescolaire":
        return level_name.split(" (", 1)[0]
    if cycle_code == "lycee_technique":
        return f"{level_name} technique"
    return level_name


def ensure_standard_levels(school, cycles=None):
    """Créer uniquement les cycles et niveaux absents, sans rien renommer.

    Ne jamais réactiver un niveau ou un cycle volontairement archivé.
    Les codes sont stables pour ne pas casser les références historiques.
    """
    created_levels = {}
    for cycle_code in enabled_standard_cycles(school, cycles):
        cycle, _ = AcademicCycle.objects.get_or_create(
            school=school, code=cycle_code,
            defaults={"name": CYCLE_LABELS[cycle_code], "order": len(created_levels) + 1},
        )
        created_levels[cycle_code] = []
        for index, (level_code, level_name) in enumerate(CLASS_LEVELS[cycle_code], start=1):
            level, _ = AcademicLevel.objects.get_or_create(
                school=school, cycle=cycle, code=level_code,
                defaults={"name": level_name, "order": index},
            )
            base_name = (
                default_class_base(cycle_code, level_name)
                if level.name == level_name else level.name
            )
            created_levels[cycle_code].append((level, base_name))
    return created_levels


def ensure_standard_classes(school, year, cycles=None):
    """Créer au plus une classe par niveau ouvert hors lycée dans l'année choisie.

    L'appelant verrouille l'école via select_for_update pour garantir
    l'idempotence en cas d'appels concurrents. Une division renommée ou
    archivée reste une division existante; elle n'est jamais recréée.
    """
    if year.school_id != school.pk or not year.active or year.status == AcademicYear.STATUS_CLOSED:
        raise ValueError("L'année scolaire n'est pas modifiable.")

    levels = ensure_standard_levels(school, cycles)
    existing = list(AcademicClass.objects.filter(school=school, year=year))
    represented = {room.level_id for room in existing}
    names = {room.name.casefold() for room in existing}
    codes = {room.code for room in existing}
    created = []

    for cycle_code, defaults in levels.items():
        # Au lycée, une Seconde/Première/Terminale A générique serait une classe fantôme.
        # Les séries proposées sont ouvertes explicitement par la direction.
        if cycle_code in ("lycee_general", "lycee_technique"):
            continue
        for level, base in defaults:
            if level.pk in represented or not level.active or not level.cycle.active:
                continue
            for index in range(1, 501):
                suffix = chr(64 + index) if index <= 26 else str(index)
                name = f"{base[:119 - len(suffix)].rstrip()} {suffix}"
                code = (f"presc-{level.code}-{suffix.lower()}" if cycle_code == "prescolaire"
                        else f"std-{cycle_code}-{level.code}-{suffix.lower()}")
                if name.casefold() not in names and code not in codes and len(code) <= 40:
                    break
            else:
                raise ValueError("Aucun nom de classe standard disponible.")
            room = AcademicClass(school=school, year=year, level=level,
                                 code=code, name=name, active=True)
            room.full_clean()
            room.save()
            created.append(room)
            represented.add(level.pk)
            names.add(name.casefold())
            codes.add(code)
    return created
