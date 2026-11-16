"""Year- and level-specific mastery criteria for the primary cycle."""
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import AcademicLevel, AcademicYear
from .calendar_views import uid
from .cycle_scope import calendar_assignments, is_calendar_teacher, scoped_cycle_ids
from .models import SchoolSetting
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
