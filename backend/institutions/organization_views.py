"""Organigrammes scolaires : nominations par école et cycle, sans escalade de droits."""
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods
from accounts.views import authorized

from .models import SchoolAppointment, SchoolMember
from .school_functions import MATERNELLE_ALIASES, function_label, positions_for_school, validate_position
from .school_profiles import CYCLE_LABELS
from .staff_models import StaffRecord
from .services import has_permission
from .views import access, log_event, parse_body, refuse


def _gate(request, school_id, permission):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, permission):
        return None, refuse()
    return school, None


def _date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Date au format AAAA-MM-JJ requise.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Date invalide.") from None
    if parsed.isoformat() != value:
        raise ValueError("Date au format AAAA-MM-JJ requise.")
    return parsed


def _validation_error(exc):
    if hasattr(exc, "message_dict"):
        items = [str(message) for messages in exc.message_dict.values() for message in messages]
    else:
        items = [str(message) for message in exc.messages]
    return JsonResponse({"error": " ".join(items)[:500]}, status=422)


def _represent(appointment, school):
    record = appointment.staff
    return {
        "id": str(appointment.pk),
        "staff": str(record.pk),
        "staff_name": " ".join((record.first_name, record.last_name)).strip(),
        "staff_code": record.staff_code,
        "has_account": bool(record.account_id),
        "function_code": appointment.function_code,
        "function_label": function_label(school, appointment.function_code),
        "cycle_code": appointment.cycle_code,
        "cycle_label": CYCLE_LABELS.get(appointment.cycle_code) if appointment.cycle_code else "Établissement entier",
        "starts_on": appointment.starts_on.isoformat() if appointment.starts_on else None,
        "ends_on": appointment.ends_on.isoformat() if appointment.ends_on else None,
        "active": appointment.active,
        "effective": appointment.is_effective,
        "revision": appointment.revision,
    }


@require_GET
@authorized
def positions(request, school_id):
    school, error = _gate(request, school_id, "school.organization.read")
    if error is not None:
        return error
    return JsonResponse({
        "school_type": school.school_type,
        "education_cycles": school.education_cycles,
        "cycle_labels": CYCLE_LABELS,
        "positions": positions_for_school(school),
        "notice": "Une nomination ne crée ni rôle applicatif ni accès à d'autres cycles.",
    })


@require_http_methods(["GET", "POST"])
@authorized
def appointments(request, school_id):
    permission = "school.organization.read" if request.method == "GET" else "school.organization.manage"
    school, error = _gate(request, school_id, permission)
    if error is not None:
        return error
    if request.method == "GET":
        qs = SchoolAppointment.objects.filter(school=school).select_related(
            "staff", "staff__account"
        ).order_by("function_code", "cycle_code", "staff__last_name")
        records = StaffRecord.objects.filter(school=school).order_by("last_name", "first_name")[:500]
        return JsonResponse({
            "appointments": [_represent(row, school) for row in qs[:500]],
            "staff_options": [{
                "id": str(row.pk),
                "name": " ".join((row.first_name, row.last_name)).strip(),
                "staff_code": row.staff_code,
                "active": row.active,
                "has_account": bool(row.account_id),
            } for row in records],
        })

    body, error = parse_body(request)
    if error is not None:
        return error
    allowed = {"staff", "function_code", "cycle_code", "starts_on", "ends_on"}
    if set(body) - allowed or not {"staff", "function_code"} <= set(body):
        return JsonResponse({"error": "Champs de nomination invalides."}, status=422)
    try:
        staff_id = UUID(str(body["staff"]))
    except (TypeError, ValueError, AttributeError):
        return JsonResponse({"error": "Personnel invalide."}, status=422)
    code = body["function_code"]
    cycle = body.get("cycle_code", "")
    if not isinstance(code, str) or not isinstance(cycle, str):
        return JsonResponse({"error": "Fonction ou cycle invalide."}, status=422)
    if len(code) > 48 or len(cycle) > 32:
        return JsonResponse({"error": "Fonction ou cycle trop long."}, status=422)
    code, cycle = code.strip(), cycle.strip()
    try:
        if school.school_type == "maternelle" and code in MATERNELLE_ALIASES:
            raise ValueError("Choisissez la fonction regroupée proposée dans l’organigramme.")
        validate_position(school, code, cycle)
        start, end = _date(body.get("starts_on")), _date(body.get("ends_on"))
        if start and end and start > end:
            raise ValueError("La fin de fonction précède son début.")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            # Same school lock as other administrative mutations.
            from .models import School
            School.objects.select_for_update().get(pk=school.pk)
            record = StaffRecord.objects.filter(school=school, pk=staff_id, active=True).first()
            if record is None:
                return JsonResponse({"error": "Personnel absent ou archivé dans cette école."}, status=422)
            equivalents = Q(function_code=code, cycle_code=cycle)
            if school.school_type == "maternelle":
                equivalents |= Q(function_code__in=[
                    alias for alias, canonical in MATERNELLE_ALIASES.items() if canonical == code
                ])
            if SchoolAppointment.objects.filter(equivalents, school=school, staff=record).exists():
                return JsonResponse({"error": "Nomination déjà enregistrée ; modifiez-la plutôt."}, status=409)
            obj = SchoolAppointment(
                school=school, staff=record, function_code=code, cycle_code=cycle,
                starts_on=start, ends_on=end, appointed_by=request.user,
            )
            obj.full_clean()
            obj.save()
            log_event(school, request, "school_post_appointed", obj.pk)
    except ValidationError as exc:
        return _validation_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Nomination déjà existante."}, status=409)
    return JsonResponse(_represent(obj, school), status=201)


@require_http_methods(["GET", "PATCH"])
@authorized
def appointment_detail(request, school_id, appointment_id):
    permission = "school.organization.read" if request.method == "GET" else "school.organization.manage"
    school, error = _gate(request, school_id, permission)
    if error is not None:
        return error
    if request.method == "GET":
        obj = SchoolAppointment.objects.select_related("staff").filter(school=school, pk=appointment_id).first()
        return JsonResponse(_represent(obj, school)) if obj else JsonResponse({"error": "Nomination introuvable."}, status=404)
    body, error = parse_body(request)
    if error is not None:
        return error
    if not set(body) <= {"revision", "active", "starts_on", "ends_on"} or not (
        set(body) - {"revision"}
    ) or type(body.get("revision")) is not int or body["revision"] < 1:
        return JsonResponse({"error": "Révision ou modification invalide."}, status=422)
    changes = {}
    if "active" in body:
        if type(body["active"]) is not bool:
            return JsonResponse({"error": "Statut invalide."}, status=422)
        changes["active"] = body["active"]
    try:
        for field in ("starts_on", "ends_on"):
            if field in body:
                changes[field] = _date(body[field])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            obj = SchoolAppointment.objects.select_for_update().select_related("staff").filter(
                school=school, pk=appointment_id
            ).first()
            if obj is None:
                return JsonResponse({"error": "Nomination introuvable."}, status=404)
            if obj.revision != body["revision"]:
                return JsonResponse({"error": "Conflit de version.", "revision": obj.revision}, status=409)
            for field, value in changes.items():
                setattr(obj, field, value)
            obj.full_clean()
            obj.revision += 1
            obj.save()
            log_event(school, request, "school_post_updated", obj.pk)
    except ValidationError as exc:
        return _validation_error(exc)
    return JsonResponse(_represent(obj, school))


@require_GET
@authorized
def my_appointments(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not SchoolMember.objects.filter(
        school=school, user=request.user, active=True,
    ).exists():
        return JsonResponse({"appointments": []})
    qs = SchoolAppointment.objects.select_related("staff").filter(
        school=school, staff__account=request.user, staff__active=True, active=True,
    ).order_by("function_code", "cycle_code")
    return JsonResponse({
        "appointments": [_represent(row, school) for row in qs[:100] if row.is_effective],
    })
