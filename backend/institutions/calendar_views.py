"""Calendrier pédagogique : événements, vacances et jalons configurables par établissement.

Ne pilote pas automatiquement les bulletins, les notes ou les finances.
L'année reste l'unité historique existante ; aucune période n'est dupliquée.
"""
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import AcademicYear, AcademicCycle, PedagogicalCalendarEvent
from .cycle_scope import scoped_cycle_ids
from .models import School
from .services import has_permission
from .views import access, log_event, parse_body, refuse

EDITABLE = {
    "title", "kind", "scope", "start_date", "end_date",
    "description", "source", "source_url", "active",
}


def uid(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def serialize(row):
    return {
        "id": str(row.pk), "year": str(row.year_id),
        "title": row.title, "kind": row.kind, "scope": row.scope,
        "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(),
        "description": row.description, "source": row.source,
        "source_url": row.source_url, "active": row.active, "revision": row.revision,
    }


def validate(data, school, *, create=False):
    if not isinstance(data, dict):
        raise ValueError("Champs de calendrier invalides.")
    required = {"title", "kind", "scope", "start_date", "end_date"} if create else set()
    if create and not required <= set(data):
        raise ValueError("Titre, catégorie, cycle et dates obligatoires.")
    if set(data) - EDITABLE:
        raise ValueError("Champs inconnus ou non modifiables.")
    clean = {}
    valid_kinds = {value for value, _ in PedagogicalCalendarEvent.KIND_CHOICES}
    valid_scopes = {value for value, _ in PedagogicalCalendarEvent.SCOPE_CHOICES}
    valid_sources = {value for value, _ in PedagogicalCalendarEvent.SOURCE_CHOICES}
    for key, value in data.items():
        if key in ("title", "description", "source_url"):
            limit = {"title": 160, "description": 500, "source_url": 500}[key]
            if not isinstance(value, str) or len(value.strip()) > limit:
                raise ValueError("Texte trop long ou invalide.")
            if key == "title" and not value.strip():
                raise ValueError("Titre de l'événement obligatoire.")
            clean[key] = value.strip()
        elif key in ("start_date", "end_date"):
            if not isinstance(value, str):
                raise ValueError("Date ISO attendue.")
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError()
            except ValueError:
                raise ValueError("Date ISO invalide.") from None
            clean[key] = parsed
        elif key == "kind":
            if value not in valid_kinds:
                raise ValueError("Catégorie de calendrier inconnue.")
            clean[key] = value
        elif key == "source":
            if value not in valid_sources:
                raise ValueError("Origine de référence inconnue.")
            clean[key] = value
        elif key == "scope":
            if value not in valid_scopes or (value != "all" and value not in (school.education_cycles or [])):
                raise ValueError("Cycle indisponible pour cette école.")
            clean[key] = value
        elif key == "active":
            if type(value) is not bool:
                raise ValueError("Statut d'archivage invalide.")
            clean[key] = value
    if not clean:
        raise ValueError("Aucune modification du calendrier.")
    return clean


def validation_error(exc):
    if hasattr(exc, "message_dict"):
        messages = [msg for values in exc.message_dict.values() for msg in values]
    else:
        messages = exc.messages
    return JsonResponse({"error": " ".join(messages)[:500]}, status=422)


def can_manage(request, school):
    return (has_permission(request.user, school, "school.academic.manage")
            and scoped_cycle_ids(request.user, school) is None)


@require_http_methods(["GET", "POST"])
@authorized
def events(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.academic.read"):
        return refuse()
    if request.method == "POST" and not can_manage(request, school):
        return refuse()
    if request.method == "GET":
        year = AcademicYear.objects.filter(school=school, pk=uid(request.GET.get("year"))).first()
        if year is None:
            return JsonResponse({"error": "Année scolaire introuvable."}, status=404)
        query = PedagogicalCalendarEvent.objects.filter(school=school, year=year)
        scope = scoped_cycle_ids(request.user, school)
        if scope is not None:
            codes = list(AcademicCycle.objects.filter(school=school, pk__in=scope).values_list("code", flat=True))
            query = query.filter(Q(scope="all") | Q(scope__in=codes))
        return JsonResponse({
            "year": str(year.pk), "events": [serialize(row) for row in query[:500]],
            "can_manage": can_manage(request, school) and year.active and year.status != AcademicYear.STATUS_CLOSED,
            "kinds": [{"code": c, "label": label} for c, label in PedagogicalCalendarEvent.KIND_CHOICES],
            "scopes": [{"code": c, "label": label} for c, label in PedagogicalCalendarEvent.SCOPE_CHOICES
                       if c == "all" or c in (school.education_cycles or [])],
        })

    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or "year" not in data:
        return JsonResponse({"error": "Année scolaire requise."}, status=422)
    year_id = uid(data.get("year"))
    try:
        clean = validate({k: v for k, v in data.items() if k != "year"}, school, create=True)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            year = AcademicYear.objects.select_for_update().filter(school=school, pk=year_id).first()
            if year is None:
                return JsonResponse({"error": "Année scolaire introuvable."}, status=404)
            if not year.active or year.status == AcademicYear.STATUS_CLOSED:
                return JsonResponse({"error": "L'année est clôturée et son calendrier figé."}, status=409)
            row = PedagogicalCalendarEvent(school=school, year=year, **clean)
            row.full_clean()
            row.save()
            log_event(school, request, "pedagogical_calendar_event_created", str(row.pk), {"year": str(year.pk)})
    except ValidationError as exc:
        return validation_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Conflit d'enregistrement du calendrier."}, status=409)
    return JsonResponse(serialize(row), status=201)


@require_http_methods(["PATCH"])
@authorized
def event_detail(request, school_id, event_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not can_manage(request, school):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or type(data.get("revision")) is not int:
        return JsonResponse({"error": "Révision de l'événement requise."}, status=422)
    try:
        clean = validate({k: v for k, v in data.items() if k != "revision"}, school)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            row = PedagogicalCalendarEvent.objects.select_for_update().select_related("year").filter(
                school=school, pk=event_id).first()
            if row is None:
                return JsonResponse({"error": "Événement introuvable."}, status=404)
            if not row.year.active or row.year.status == AcademicYear.STATUS_CLOSED:
                return JsonResponse({"error": "Année clôturée : le calendrier est conservé en lecture seule."}, status=409)
            if row.revision != data["revision"]:
                return JsonResponse({"error": "Conflit de version.", "revision": row.revision}, status=409)
            for key, value in clean.items():
                setattr(row, key, value)
            row.full_clean()
            row.revision += 1
            row.save()
            log_event(school, request, "pedagogical_calendar_event_updated", str(row.pk), {
                "year": str(row.year_id), "active": row.active,
            })
    except ValidationError as exc:
        return validation_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Modification impossible."}, status=409)
    return JsonResponse(serialize(row))
