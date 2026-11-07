"""Module 04: institutional academic structure; all lookups school-scoped."""
import re
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import (
    AcademicYear, AcademicCycle, AcademicLevel, AcademicTrack, AcademicClass, AcademicPeriod,
)
from .cycle_scope import scoped_cycle_ids
from .services import can_manage_classes, has_permission
from .student_models import Enrollment
from .views import access, delete_unused, log_event, parse_body, refuse

RESOURCES = {
    "years": (AcademicYear, ("code", "name", "start_date", "end_date", "active")),
    "cycles": (AcademicCycle, ("code", "name", "order", "active")),
    "levels": (AcademicLevel, ("code", "name", "cycle", "order", "active")),
    "tracks": (AcademicTrack, ("code", "name", "level", "order", "active")),
    "classes": (AcademicClass, ("code", "name", "year", "level", "track", "capacity", "active")),
    "periods": (AcademicPeriod, ("code", "name", "year", "start_date", "end_date", "order", "active")),
}
RELATIONS = {
    "year": AcademicYear, "cycle": AcademicCycle, "level": AcademicLevel, "track": AcademicTrack,
}
REQUIRED = {
    "years": {"code", "name", "start_date", "end_date"},
    "cycles": {"code", "name"},
    "levels": {"code", "name", "cycle"},
    "tracks": {"code", "name", "level"},
    "classes": {"code", "name", "year", "level"},
    "periods": {"code", "name", "year", "start_date", "end_date"},
}
IMMUTABLE_RELATIONS = {"year", "cycle", "level", "track"}


def scoped_resources(query, resource, user, school):
    cycles = scoped_cycle_ids(user, school)
    if cycles is None:
        return query
    lookups = {
        "cycles": "id__in", "levels": "cycle_id__in",
        "tracks": "level__cycle_id__in", "classes": "level__cycle_id__in",
    }
    # Les années sont des métadonnées globales sans dossier personnel.
    return query.filter(**{lookups[resource]: cycles}) if resource in lookups else query


def describe(obj, fields):
    result = {"id": str(obj.pk), "revision": obj.revision}
    for key in fields:
        value = getattr(obj, key + "_id" if key in RELATIONS else key)
        if isinstance(value, date):
            value = value.isoformat()
        elif isinstance(value, UUID):
            value = str(value)
        result[key] = value
    return result


def validate_fields(data, school, resource, *, editing=False):
    _, fields = RESOURCES[resource]
    allowed = set(fields)
    if editing:
        allowed -= IMMUTABLE_RELATIONS
    unknown = set(data) - allowed - ({"revision"} if editing else set())
    if unknown:
        raise ValueError("Champs non modifiables ou inconnus.")
    if not editing and not REQUIRED[resource] <= set(data):
        raise ValueError("Champs obligatoires manquants.")
    if editing and not (set(data) - {"revision"}):
        raise ValueError("Aucune modification.")
    clean = {}
    for key, value in data.items():
        if key == "revision":
            continue
        if key == "code":
            if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", value):
                raise ValueError("Code invalide (lettres minuscules, chiffres, _ et -).")
        elif key == "name":
            if not isinstance(value, str) or not (1 <= len(value.strip()) <= 120):
                raise ValueError("Nom invalide.")
            value = value.strip()
        elif key in ("start_date", "end_date"):
            if not isinstance(value, str):
                raise ValueError("Date ISO requise.")
            try:
                value = date.fromisoformat(value)
                if value.isoformat() != data[key]:
                    raise ValueError()
            except ValueError:
                raise ValueError("Date ISO invalide.") from None
        elif key in ("order", "capacity"):
            if value is None and key == "capacity":
                pass
            elif type(value) is not int or not (0 <= value <= 1000 if key == "order" else 1 <= value <= 5000):
                raise ValueError("Ordre ou capacité invalide.")
        elif key == "active":
            if type(value) is not bool:
                raise ValueError("Statut invalide.")
        elif key in RELATIONS:
            if key == "track" and value is None:
                clean[key + "_id"] = None
                continue
            try:
                uid = UUID(value)
            except (ValueError, TypeError, AttributeError):
                raise ValueError("Identifiant de rattachement invalide.") from None
            target = RELATIONS[key].objects.filter(school=school, pk=uid).first()
            if target is None:
                raise ValueError("Rattachement introuvable dans cette école.")
            clean[key + "_id"] = target.pk
            continue
        clean[key] = value
    return clean


def model_error(exc):
    if hasattr(exc, "message_dict"):
        parts = [m for group in exc.message_dict.values() for m in group]
    else:
        parts = exc.messages
    return JsonResponse({"error": " ".join(parts)[:500]}, status=422)


def class_name_taken(school, year_id, name, *, exclude=None):
    names = AcademicClass.objects.filter(school=school, year_id=year_id).exclude(pk=exclude)
    return any(existing.casefold() == name.casefold() for existing in names.values_list("name", flat=True))


def duplicate_class_name():
    return JsonResponse({"error": "Ce nom de classe est déjà utilisé pour cette année."}, status=409)


@require_http_methods(["GET", "POST"])
@authorized
def collection(request, school_id, resource):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if resource not in RESOURCES:
        return JsonResponse({"error": "Ressource introuvable."}, status=404)
    permission = "school.academic.read" if request.method == "GET" else "school.academic.manage"
    if not (can_manage_classes(request.user, school) if resource == "classes" and request.method != "GET"
            else has_permission(request.user, school, permission)):
        return refuse()
    model, fields = RESOURCES[resource]
    if request.method == "GET":
        rows = scoped_resources(model.objects.filter(school=school), resource, request.user, school).order_by("name", "pk")[:500]
        return JsonResponse({resource: [describe(o, fields) for o in rows]})
    data, error = parse_body(request)
    if error is not None:
        return error
    try:
        clean = validate_fields(data, school, resource)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            if resource == "periods":
                # Serialize competing period creations for the same school year.
                AcademicYear.objects.select_for_update().get(school=school, pk=clean["year_id"])
            if resource == "classes":
                level = AcademicLevel.objects.select_related("cycle").get(school=school, pk=clean["level_id"])
                if not can_manage_classes(request.user, school, level.cycle.code):
                    return refuse()
                AcademicYear.objects.select_for_update(no_key=True).get(school=school, pk=clean["year_id"])
                if class_name_taken(school, clean["year_id"], clean["name"]):
                    return duplicate_class_name()
            obj = model(school=school, **clean)
            obj.full_clean()
            obj.save()
            log_event(school, request, "academic_created", f"{resource}:{obj.pk}")
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Code déjà utilisé."}, status=409)
    return JsonResponse(describe(obj, fields), status=201)


@require_http_methods(["GET", "PATCH", "DELETE"])
@authorized
def detail(request, school_id, resource, object_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if resource not in RESOURCES:
        return JsonResponse({"error": "Ressource introuvable."}, status=404)
    if request.method == "DELETE" and resource != "classes":
        return JsonResponse({"error": "Archivage uniquement pour cette ressource."}, status=405)
    permission = "school.academic.read" if request.method == "GET" else "school.academic.manage"
    if not (can_manage_classes(request.user, school) if resource == "classes" and request.method != "GET"
            else has_permission(request.user, school, permission)):
        return refuse()
    model, fields = RESOURCES[resource]
    if request.method == "GET":
        obj = scoped_resources(model.objects.filter(school=school, pk=object_id), resource, request.user, school).first()
        if not obj:
            return JsonResponse({"error": "Objet introuvable."}, status=404)
        return JsonResponse(describe(obj, fields))
    data, error = parse_body(request)
    if error is not None:
        return error
    if request.method == "DELETE":
        try:
            with transaction.atomic():
                classroom = AcademicClass.objects.select_for_update().filter(school=school, pk=object_id).first()
                if classroom is None:
                    return JsonResponse({"error": "Classe introuvable."}, status=404)
                if not can_manage_classes(request.user, school, classroom.level.cycle.code):
                    return refuse()
                return delete_unused(request, school, classroom, data, "academic_class_deleted")
        except IntegrityError:
            return JsonResponse({"error": "Cette classe est utilisée. Vous pouvez l’archiver pour garder son historique."}, status=409)
    revision = data.get("revision")
    if type(revision) is not int or revision < 1:
        return JsonResponse({"error": "Révision obligatoire."}, status=422)
    try:
        clean = validate_fields(data, school, resource, editing=True)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            obj = model.objects.select_for_update().filter(school=school, pk=object_id).first()
            if not obj:
                return JsonResponse({"error": "Objet introuvable."}, status=404)
            if resource == "classes" and not can_manage_classes(request.user, school, obj.level.cycle.code):
                return refuse()
            if obj.revision != revision:
                return JsonResponse({"error": "Conflit de version.", "revision": obj.revision}, status=409)
            if resource == "periods":
                AcademicYear.objects.select_for_update().get(school=school, pk=obj.year_id)
            if resource == "classes" and "name" in clean and clean["name"] != obj.name:
                AcademicYear.objects.select_for_update(no_key=True).get(school=school, pk=obj.year_id)
                if class_name_taken(school, obj.year_id, clean["name"], exclude=obj.pk):
                    return duplicate_class_name()
            if resource == "classes" and clean.get("capacity") is not None and clean["capacity"] != obj.capacity:
                enrolled = Enrollment.objects.filter(school=school, classroom=obj, active=True).count()
                if clean["capacity"] < enrolled:
                    return JsonResponse({"error": f"Cette classe compte déjà {enrolled} élèves inscrits."}, status=422)
            for key, value in clean.items():
                setattr(obj, key, value)
            obj.full_clean()
            obj.revision += 1
            obj.save()
            log_event(school, request, "academic_updated", f"{resource}:{obj.pk}")
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Code déjà utilisé."}, status=409)
    return JsonResponse(describe(obj, fields))
