"""Year- and level-specific mastery criteria for the primary cycle."""
from collections import defaultdict

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import AcademicClass, AcademicLevel, AcademicPeriod, AcademicYear
from .calendar_views import uid
from .cycle_scope import calendar_assignments, is_calendar_teacher, scoped_cycle_ids
from .models import SchoolSetting
from .primary_models import PrimaryMastery
from .student_models import Enrollment
from .services import has_permission, key_for_scope, resolve_settings
from .views import access, log_event, parse_body, refuse, string


def clean_criteria(value):
    if not isinstance(value, list) or len(value) > 30:
        raise ValueError("Le référentiel accepte jusqu’à 30 critères.")
    clean = []
    seen = set()
    for row in value:
        if (not isinstance(row, dict) or set(row) != {"id", "label", "remediation"}
                or not uid(row["id"]) or not string(row["label"], 120)
                or not isinstance(row["remediation"], str) or len(row["remediation"].strip()) > 300):
            raise ValueError("Critère ou piste de remédiation invalide.")
        identifier = str(uid(row["id"]))
        if identifier in seen:
            raise ValueError("Chaque critère doit avoir un identifiant distinct.")
        seen.add(identifier)
        clean.append({"id": identifier, "label": row["label"].strip(),
                      "remediation": row["remediation"].strip()})
    return clean


@require_http_methods(["GET", "PATCH"])
@authorized
def criteria(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.academic.read"):
        return refuse()
    editing = request.method == "PATCH"
    can_edit = has_permission(request.user, school, "school.settings.write")
    if editing and not can_edit:
        return refuse()
    if editing:
        data, error = parse_body(request)
        if error is not None:
            return error
        if set(data) != {"year", "level", "revision", "criteria"} or type(data["revision"]) is not int or data["revision"] < 0:
            return JsonResponse({"error": "Révision ou périmètre invalide."}, status=422)
        try:
            clean = clean_criteria(data["criteria"])
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=422)
    else:
        data = request.GET

    years = AcademicYear.objects.filter(school=school, pk=uid(data.get("year")))
    levels = AcademicLevel.objects.select_related("cycle").filter(
        school=school, cycle__school=school, cycle__code="primaire", active=True, cycle__active=True,
    )
    scope_ids = scoped_cycle_ids(request.user, school)
    if scope_ids is not None:
        levels = levels.filter(cycle_id__in=scope_ids)

    with transaction.atomic():
        year = (years.select_for_update() if editing else years).first()
        if year is None:
            return JsonResponse({"error": "Année introuvable."}, status=404)
        if is_calendar_teacher(request.user, school):
            assignments = calendar_assignments(request.user, school).filter(year=year, duty="enseignant")
            levels = levels.filter(pk__in=assignments.values("classroom__level_id"))
        if not editing and "level" not in data:
            return JsonResponse({"levels": list(levels.order_by("order", "name", "pk").values("id", "name"))})
        level = levels.filter(pk=uid(data.get("level"))).first()
        if level is None:
            return JsonResponse({"error": "Niveau primaire introuvable."}, status=404)
        scope = {"year": year.code, "cycle": level.cycle.code, "level": level.code}
        key = key_for_scope(scope)
        settings = SchoolSetting.objects.filter(school=school, scope_key=key)
        current = (settings.select_for_update() if editing else settings).first()
        revision = current.revision if current else 0
        editable = can_edit and year.active and year.status != AcademicYear.STATUS_CLOSED
        if not editing:
            effective, _ = resolve_settings(school, scope)
            try:
                content = clean_criteria(effective.get("primary_mastery_criteria", []))
            except ValueError:
                content = []
            return JsonResponse({"criteria": content, "revision": revision, "editable": editable})
        if not editable:
            return JsonResponse({"error": "Le référentiel de cette année est figé."}, status=409)
        if data["revision"] != revision:
            return JsonResponse({"error": "Conflit de version.", "revision": revision}, status=409)
        setting = current or SchoolSetting(school=school, scope=scope, scope_key=key)
        setting.values = {**setting.values, "primary_mastery_criteria": clean}
        setting.revision = revision + 1
        setting.save()
        log_event(school, request, "primary_mastery_criteria_updated", key, {"revision": setting.revision})
    return JsonResponse({"criteria": clean, "revision": setting.revision, "editable": True})

def mastery_output(mark):
    return {
        "criterion": str(mark.criterion_id), "snapshot": mark.criterion_snapshot,
        "stage": mark.stage, "remediation_status": mark.remediation_status,
        "follow_up": mark.follow_up, "revision": mark.revision,
    }


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def mastery(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.academic.read"):
        return refuse()

    editing = request.method == "PATCH"
    if editing:
        data, error = parse_body(request)
        if error is not None:
            return error
        fields = {"year", "classroom", "milestone", "enrollment", "criterion", "stage",
                  "remediation_status", "follow_up", "revision"}
        if (set(data) != fields or type(data["revision"]) is not int or data["revision"] < 0
                or not isinstance(data["stage"], str) or data["stage"] not in PrimaryMastery.STAGES
                or not isinstance(data["remediation_status"], str)
                or (data["remediation_status"] and data["remediation_status"] not in PrimaryMastery.REMEDIATION)
                or not isinstance(data["follow_up"], str) or len(data["follow_up"].strip()) > 500):
            return JsonResponse({"error": "Évaluation, remédiation ou révision invalide."}, status=422)
    else:
        data = request.GET

    year_query = AcademicYear.objects.filter(school=school, pk=uid(data.get("year")))
    with transaction.atomic():
        year = (year_query.select_for_update() if editing else year_query).first()
        if year is None:
            return JsonResponse({"error": "Année introuvable."}, status=404)
        rooms = AcademicClass.objects.filter(
            school=school, year=year, level__school=school, level__cycle__school=school,
            level__cycle__code="primaire", active=True,
        )
        scope = scoped_cycle_ids(request.user, school)
        if scope is not None:
            rooms = rooms.filter(level__cycle_id__in=scope)
        if not has_permission(request.user, school, "school.academic.manage"):
            assignments = calendar_assignments(request.user, school).filter(year=year, duty="enseignant")
            rooms = rooms.filter(pk__in=assignments.values("classroom_id"))
        milestones = AcademicPeriod.objects.filter(
            school=school, year=year, kind=AcademicPeriod.MILESTONE,
            cycle_id__in=rooms.values("level__cycle_id"),
        )
        if not editing and "classroom" not in data:
            return JsonResponse({
                "classrooms": list(rooms.order_by("name", "pk").values("id", "name")),
                "milestones": list(milestones.order_by("start_date", "pk").values("id", "name", "closed")),
            })
        room = rooms.select_related("level").filter(pk=uid(data.get("classroom"))).first()
        if room is None:
            return JsonResponse({"error": "Classe primaire introuvable."}, status=404)
        period = milestones.filter(pk=uid(data.get("milestone")), cycle_id=room.level.cycle_id)
        period = (period.select_for_update() if editing else period).first()
        if period is None:
            return JsonResponse({"error": "Palier introuvable pour cette classe."}, status=404)
        editable = year.active and year.status != AcademicYear.STATUS_CLOSED and period.active and not period.closed
        scope = {"year": year.code, "cycle": "primaire", "level": room.level.code}
        try:
            reference = clean_criteria(resolve_settings(school, scope)[0].get("primary_mastery_criteria", []))
        except ValueError:
            reference = []
        roster = Enrollment.objects.filter(
            school=school, year=year, classroom=room, active=True, student__school=school,
            student__active=True, enrolled_on__lte=period.end_date,
        )
        marks = PrimaryMastery.objects.filter(
            classroom=room, milestone=period, enrollment__school=school, enrollment__year=year,
            enrollment__student__school=school,
        )
        if not editing:
            active = {enrollment.pk: enrollment for enrollment in roster.select_related("student")}
            people = dict(active)
            entries = defaultdict(list)
            for mark in marks.select_related("enrollment__student").order_by("criterion_id"):
                people[mark.enrollment_id] = mark.enrollment
                entries[mark.enrollment_id].append(mastery_output(mark))
            rows = sorted(people.values(), key=lambda row: (row.student.last_name, row.student.first_name, row.pk))
            return JsonResponse({
                "editable": editable, "criteria": reference, "stages": PrimaryMastery.STAGES,
                "remediation_statuses": PrimaryMastery.REMEDIATION,
                "students": [{"enrollment": str(row.pk), "name": f"{row.student.last_name} {row.student.first_name}",
                              "current": row.pk in active, "marks": entries[row.pk]} for row in rows],
            })
        if not editable:
            return JsonResponse({"error": "Le suivi de ce palier est en lecture seule."}, status=409)
        enrollment = roster.select_for_update(of=("self",)).filter(pk=uid(data["enrollment"])).first()
        criterion_id = uid(data["criterion"])
        criterion = next((item for item in reference if item["id"] == str(criterion_id)), None)
        if enrollment is None or criterion is None:
            return JsonResponse({"error": "Inscription ou critère introuvable pour ce palier."}, status=404)
        mark = marks.filter(enrollment=enrollment, criterion_id=criterion_id).first()
        revision = mark.revision if mark else 0
        if data["revision"] != revision:
            return JsonResponse({"error": "Conflit de version.", "revision": revision}, status=409)
        if mark is None:
            mark = PrimaryMastery(classroom=room, milestone=period, enrollment=enrollment,
                                  criterion_id=criterion_id, criterion_snapshot=criterion)
        mark.stage = data["stage"]
        mark.remediation_status = data["remediation_status"]
        mark.follow_up = data["follow_up"].strip()
        mark.revision = revision + 1
        mark.save()
        log_event(school, request, "primary_mastery_updated", str(mark.pk), {"revision": mark.revision})
    return JsonResponse(mastery_output(mark), status=200 if revision else 201)
