"""M0/M1 — diagnostic de cohérence en lecture seule des fondations YEM.

Aucune mutation, aucun identifiant personnel ni nom d'établissement n'est affiché.
Ce diagnostic n'atteste ni la qualité des sauvegardes ni la sécurité de toutes les API.
"""
import json
from collections import defaultdict
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from institutions.academic_models import (
    AcademicClass,
    AcademicCycle,
    AcademicPeriod,
    AcademicYear,
)
from institutions.models import School, SchoolMember, SchoolRole


def foundation_audit():
    """Return aggregated findings without writing to the database."""
    critical = {}
    warnings = {}

    def record(target, code, count):
        if count:
            target[code] = int(count)

    record(
        critical,
        "member_role_other_school",
        SchoolMember.objects.exclude(role__school_id=F("school_id")).count(),
    )

    relation = SchoolMember.additional_roles.through
    record(
        critical,
        "additional_role_other_school",
        relation.objects.exclude(
            schoolrole__school_id=F("schoolmember__school_id")
        ).count(),
    )

    record(
        critical,
        "class_year_other_school",
        AcademicClass.objects.exclude(year__school_id=F("school_id")).count(),
    )
    record(
        critical,
        "class_level_other_school",
        AcademicClass.objects.exclude(level__school_id=F("school_id")).count(),
    )
    record(
        critical,
        "class_track_other_school_or_level",
        AcademicClass.objects.filter(track__isnull=False).exclude(
            track__school_id=F("school_id"),
            track__level_id=F("level_id"),
        ).count(),
    )
    record(
        critical,
        "period_year_other_school",
        AcademicPeriod.objects.exclude(year__school_id=F("school_id")).count(),
    )
    record(
        critical,
        "invalid_year_dates",
        AcademicYear.objects.filter(start_date__gte=F("end_date")).count(),
    )
    record(
        critical,
        "current_year_marked_inactive",
        AcademicYear.objects.filter(
            status=AcademicYear.STATUS_CURRENT,
            active=False,
        ).count(),
    )

    year_overlap_count = 0
    year_schools = set()
    latest_end = None
    last_school = None
    current_years = defaultdict(int)
    for school_id, status, start, end in AcademicYear.objects.order_by(
        "school_id", "start_date", "end_date"
    ).values_list("school_id", "status", "start_date", "end_date"):
        year_schools.add(school_id)
        if status == AcademicYear.STATUS_CURRENT:
            current_years[school_id] += 1
        if school_id != last_school:
            latest_end = None
            last_school = school_id
        if latest_end is not None and start <= latest_end:
            year_overlap_count += 1
        if latest_end is None or end > latest_end:
            latest_end = end
    record(critical, "overlapping_academic_years", year_overlap_count)
    record(critical, "multiple_current_years", sum(
        max(0, count - 1) for count in current_years.values()
    ))
    record(
        warnings,
        "schools_without_current_year",
        sum(1 for school_id in year_schools if current_years[school_id] == 0),
    )

    # Validate saved scopes independently of the UI; a corrupt list must not be
    # mistaken for a valid, configured group of academic cycles.
    active_cycles = defaultdict(set)
    for school_id, cycle_id in AcademicCycle.objects.filter(
        active=True
    ).values_list("school_id", "id"):
        active_cycles[school_id].add(str(cycle_id))
    invalid_scopes = 0
    for school_id, values in SchoolMember.objects.filter(
        active=True,
        access_cycle_ids__isnull=False,
    ).values_list("school_id", "access_cycle_ids"):
        valid = isinstance(values, list) and 1 <= len(values) <= 20
        normalized = []
        if valid:
            for value in values:
                try:
                    if not isinstance(value, str):
                        raise ValueError()
                    normalized.append(str(UUID(value)))
                except (ValueError, AttributeError, TypeError):
                    valid = False
                    break
        if (not valid or len(normalized) != len(set(normalized))
                or not set(normalized).issubset(active_cycles[school_id])):
            invalid_scopes += 1
    record(critical, "invalid_active_member_cycle_scopes", invalid_scopes)

    # Legacy NULL is intentionally global in YEM. The warning asks for a
    # human access review; this is NOT proof of a vulnerability.
    record(
        warnings,
        "legacy_global_members_to_review",
        SchoolMember.objects.filter(active=True, access_cycle_ids__isnull=True).count(),
    )
    record(
        warnings,
        "schools_unclassified",
        School.objects.filter(is_active=True, school_type="non_classe").count(),
    )

    # Role catalog drift is informational. A newer feature may legitimately
    # introduce permission names before an administrator updates role templates.
    from institutions.services import PERMISSIONS
    unknown_roles = 0
    for permissions in SchoolRole.objects.values_list("permissions", flat=True):
        if not isinstance(permissions, list) or (
            set(str(p) for p in permissions) - PERMISSIONS
        ):
            unknown_roles += 1
    record(warnings, "roles_with_unknown_permissions", unknown_roles)

    return {
        "version": 1,
        "mode": "read_only",
        "scope": "m0_m1_foundations_only",
        "counts": {
            "schools": School.objects.count(),
            "members": SchoolMember.objects.count(),
            "academic_years": AcademicYear.objects.count(),
        },
        "critical": critical,
        "warnings": warnings,
        "production_backup_verified": None,
    }


class Command(BaseCommand):
    help = "Audit M0/M1 en lecture seule : cohérence établissements, rôles, cycles et années."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json", action="store_true", dest="as_json",
            help="Afficher uniquement des décomptes structurés, sans données personnelles.",
        )

    def handle(self, *args, **options):
        result = foundation_audit()
        if options["as_json"]:
            self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            self.stdout.write("YEM M0/M1 — diagnostic en lecture seule")
            for key, value in result["counts"].items():
                self.stdout.write(f"  {key}: {value}")
            for kind in ("critical", "warnings"):
                self.stdout.write(f"  {kind}:")
                for code, count in sorted(result[kind].items()):
                    self.stdout.write(f"    {code}: {count}")
                if not result[kind]:
                    self.stdout.write("    aucun")
            self.stdout.write(
                "Sauvegarde de production non vérifiée par cette commande."
            )
        if result["critical"]:
            raise CommandError(
                "Incohérences critiques détectées ; analyser et corriger "
                "sur une copie de la base avant toute intervention en production."
            )
