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

from .academic_models import AcademicYear, AcademicCycle, AcademicPeriod, PedagogicalCalendarEvent
from .academic_views import describe, RESOURCES
from .cycle_scope import pedagogical_cycle_ids
from .models import SchoolSetting
from .services import has_permission, key_for_scope, resolve_settings, valid_calendar_profile
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
    valid_scopes = {"all", *(school.education_cycles or []), *AcademicCycle.objects.filter(
        school=school, active=True,
    ).values_list("code", flat=True)}
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
            if not isinstance(value, str) or value not in valid_scopes:
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
    return has_permission(request.user, school, "school.academic.manage")


def can_write_scope(request, school, year, code):
    scope = pedagogical_cycle_ids(request.user, school, year)
    return scope is None or AcademicCycle.objects.filter(
        school=school, pk__in=scope, code=code, active=True,
    ).exclude(code="all").exists()


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
        scope = pedagogical_cycle_ids(request.user, school, year)
        cycles = AcademicCycle.objects.filter(school=school).order_by("order", "name", "pk")
        if scope is not None:
            cycles = cycles.filter(pk__in=scope)
        chosen = request.GET.get("cycle")
        cycle = cycles.filter(pk=uid(chosen)).first() if chosen else None
        if chosen and cycle is None:
            return JsonResponse({"error": "Cycle introuvable."}, status=404)
        periods = AcademicPeriod.objects.filter(school=school, year=year)
        open_year = year.active and year.status != AcademicYear.STATUS_CLOSED
        profile = {}
        profile_scope = None
        profile_revision = 0
        layers = []
        if cycle:
            query = query.filter(Q(scope="all") | Q(scope=cycle.code))
            periods = periods.filter(Q(cycle=cycle) | Q(cycle__isnull=True))
            profile_scope = {"year": year.code, "cycle": cycle.code}
            effective, layers = resolve_settings(school, profile_scope)
            profile_revision = next((layer["revision"] for layer in layers if layer["scope"] == profile_scope), 0)
            profile = effective.get("calendar_profile", {})
            if not valid_calendar_profile(profile):
                profile = {}
        else:
            if scope is not None:
                query = query.filter(Q(scope="all") | Q(scope__in=cycles.values("code")))
            periods = periods.filter(cycle__isnull=True)
        periods = periods.order_by("start_date", "order", "pk")
        published_ids = set(periods.filter(reports__status="published").values_list("pk", flat=True))
        cycle_choices = dict(PedagogicalCalendarEvent.SCOPE_CHOICES)
        valid_codes = set(school.education_cycles or []) if scope is None else set()
        for item in cycles:
            cycle_choices[item.code] = item.name
            if item.active:
                valid_codes.add(item.code)
        return JsonResponse({
            "cycles": list(cycles.values("id", "code", "name", "active")),
            "periods": [
                dict(describe(period, RESOURCES["periods"][1]), frozen=period.closed or period.pk in published_ids,
                     historical=period.cycle_id is None)
                for period in periods
            ],
            "profile": profile,
            "profile_scope": profile_scope,
            "profile_revision": profile_revision,
            "can_manage_profile": bool(cycle and cycle.active and open_year
                                       and has_permission(request.user, school, "school.settings.write")),
            "can_manage_periods": bool(open_year and (cycle.active if cycle else scope is None)
                                       and can_manage(request, school)),
            "year": str(year.pk), "events": [serialize(row) for row in query[:500]],
            "can_manage": bool(can_manage(request, school) and open_year and (scope is None or scope)),
            "can_manage_shared_events": scope is None,
            "kinds": [{"code": c, "label": label} for c, label in PedagogicalCalendarEvent.KIND_CHOICES],
            "scopes": [{"code": c, "label": label} for c, label in cycle_choices.items()
                       if (c == "all" and scope is None)
                       or (c in valid_codes and (not cycle or c == cycle.code))],
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
            year = AcademicYear.objects.select_for_update().filter(school=school, pk=year_id).first()
            if year is None:
                return JsonResponse({"error": "Année scolaire introuvable."}, status=404)
            if not year.active or year.status == AcademicYear.STATUS_CLOSED:
                return JsonResponse({"error": "L'année est clôturée et son calendrier figé."}, status=409)
            if not can_write_scope(request, school, year, clean["scope"]):
                return refuse()
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
            events_for_school = PedagogicalCalendarEvent.objects.filter(school=school, pk=event_id)
            year_id = events_for_school.values_list("year_id", flat=True).first()
            if year_id:
                AcademicYear.objects.select_for_update().get(school=school, pk=year_id)
            row = events_for_school.select_for_update().select_related("year").first()
            if row is None:
                return JsonResponse({"error": "Événement introuvable."}, status=404)
            if not row.year.active or row.year.status == AcademicYear.STATUS_CLOSED:
                return JsonResponse({"error": "Année clôturée : le calendrier est conservé en lecture seule."}, status=409)
            if not (can_write_scope(request, school, row.year, row.scope)
                    and can_write_scope(request, school, row.year, clean.get("scope", row.scope))):
                return refuse()
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


@require_http_methods(["PATCH"])
@authorized
def update_profile(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not (has_permission(request.user, school, "school.academic.read")
            and has_permission(request.user, school, "school.settings.write")):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    if (set(data) != {"year", "cycle", "revision", "profile"} or type(data["revision"]) is not int
            or data["revision"] < 0 or not valid_calendar_profile(data["profile"])):
        return JsonResponse({"error": "Profil ou révision invalide."}, status=422)

    with transaction.atomic():
        year = AcademicYear.objects.select_for_update().filter(school=school, pk=uid(data["year"])).first()
        cycle = AcademicCycle.objects.filter(school=school, pk=uid(data["cycle"]), active=True).first()
        if year is None or cycle is None or not can_write_scope(request, school, year, cycle.code):
            return JsonResponse({"error": "Année ou cycle introuvable."}, status=404)
        if not year.active or year.status == AcademicYear.STATUS_CLOSED:
            return JsonResponse({"error": "Le profil de l'année est figé."}, status=409)
        scope = {"year": year.code, "cycle": cycle.code}
        key = key_for_scope(scope)
        setting = SchoolSetting.objects.select_for_update().filter(school=school, scope_key=key).first()
        revision = setting.revision if setting else 0
        if revision != data["revision"]:
            return JsonResponse({"error": "Conflit de version.", "revision": revision}, status=409)
        values = {**(setting.values if setting else {}), "calendar_profile": data["profile"]}
        if setting is None:
            setting = SchoolSetting(school=school, scope_key=key, scope=scope)
        setting.values = values
        setting.revision = revision + 1
        setting.save()
        log_event(school, request, "pedagogical_calendar_profile_updated", key, {"revision": setting.revision})
    return JsonResponse({"profile": data["profile"], "revision": setting.revision})
