"""Ouverture explicite de classes par séries dans les lycées YEM."""
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from accounts.views import authorized

from .academic_models import AcademicClass, AcademicLevel, AcademicTrack, AcademicYear
from .models import School
from .secondary_series import SECONDARY_CYCLES, series_display_name, series_slug
from .services import can_manage_classes
from .views import access, log_event, parse_body, refuse


def as_uuid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def unique_code(name, used):
    base = (slugify(name) or "classe")[:35].strip("-") or "classe"
    candidate, index = base, 2
    while candidate in used:
        suffix = "-" + str(index)
        candidate = base[:40 - len(suffix)] + suffix
        index += 1
    return candidate


@require_POST
@authorized
def series_classes(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not can_manage_classes(request.user, school):
        return refuse()
    body, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(body, dict) or set(body) != {"year", "level", "series", "names", "capacity"}:
        return JsonResponse({"error": "Année, niveau, série, divisions et capacité requis."}, status=422)
    names = body["names"]
    if (not isinstance(names, list) or not 1 <= len(names) <= 30
            or not all(isinstance(name, str) and 1 <= len(name.strip()) <= 120 for name in names)):
        return JsonResponse({"error": "Indiquez entre 1 et 30 classes."}, status=422)
    names = [name.strip() for name in names]
    if len({name.casefold() for name in names}) != len(names):
        return JsonResponse({"error": "Les noms doivent être différents."}, status=422)
    cap = body["capacity"]
    if cap is not None and (type(cap) is not int or not 1 <= cap <= 5000):
        return JsonResponse({"error": "Capacité invalide."}, status=422)
    try:
        series = body["series"].strip() if isinstance(body["series"], str) else ""
        code = series_slug(series)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            locked = School.objects.select_for_update().get(pk=school.pk)
            year = AcademicYear.objects.select_for_update().filter(
                school=locked, pk=as_uuid(body["year"])).first()
            level = AcademicLevel.objects.select_related("cycle").filter(
                school=locked, pk=as_uuid(body["level"])).first()
            if year is None or level is None:
                return JsonResponse({"error": "Année ou niveau introuvable."}, status=404)
            cycle = level.cycle.code
            if cycle not in SECONDARY_CYCLES or cycle not in (school.education_cycles or []):
                return JsonResponse({"error": "Le lycée doit ouvrir ce cycle."}, status=422)
            if not can_manage_classes(request.user, school, cycle):
                return refuse()
            if (not year.active or year.status == AcademicYear.STATUS_CLOSED
                    or not level.active or not level.cycle.active):
                return JsonResponse({"error": "Année, niveau ou cycle archivé."}, status=409)
            existing = list(AcademicClass.objects.filter(school=school, year=year).values_list("name", "code"))
            used_names = {name.casefold() for name, _ in existing}
            if any(name.casefold() in used_names for name in names):
                return JsonResponse({"error": "Nom de classe déjà utilisé cette année."}, status=409)
            track, _ = AcademicTrack.objects.get_or_create(
                school=locked, level=level, code=code,
                defaults={"name": series_display_name(series, cycle, level.code)},
            )
            if not track.active:
                return JsonResponse({"error": "Série archivée : réactivez-la d'abord."}, status=409)
            used_codes = {code for _, code in existing}
            created = []
            for name in names:
                class_code = unique_code(name, used_codes)
                used_codes.add(class_code)
                classroom = AcademicClass(
                    school=locked, year=year, level=level, track=track,
                    code=class_code, name=name, capacity=cap,
                )
                classroom.full_clean()
                classroom.save()
                created.append(classroom)
            log_event(school, request, "secondary_series_classes_created", str(year.pk), {
                "series": str(track.pk), "class_ids": [str(item.pk) for item in created],
            })
    except (ValidationError, IntegrityError, ValueError) as exc:
        return JsonResponse({"error": str(exc)[:500]}, status=409 if isinstance(exc, IntegrityError) else 422)
    return JsonResponse({
        "series": {"id": str(track.pk), "code": track.code, "name": track.name},
        "classes": [{"id": str(item.pk), "name": item.name, "code": item.code}
                    for item in created],
    }, status=201)
