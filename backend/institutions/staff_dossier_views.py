"""Dossiers professionnels YEM : identité, fonctions, qualifications et affectations.

Aucun document privé, salaire, adresse personnelle ou identifiant de connexion.
Les fonctions dans l'organigramme ne donnent jamais une permission à elles seules.
"""
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from accounts.views import authorized
from .cycle_scope import profile_cycle_keys, scoped_cycle_ids
from .organization_models import SchoolAppointment
from .school_functions import CYCLE_LABELS, function_label
from .services import has_permission
from .staff_models import StaffAssignment, StaffProfessionalDossier, StaffRecord, StaffPhoto
from .staff_photo_views import portrait_url
from .views import access, log_event, parse_body, refuse


FIELDS = (
    "qualification", "specialty", "employment_status", "workload",
    "professional_email", "professional_phone",
)
LIMITS = {
    "qualification": 180, "specialty": 180, "employment_status": 100,
    "workload": 100, "professional_email": 254, "professional_phone": 45,
}


def _professional(dossier):
    data = {key: getattr(dossier, key) if dossier else "" for key in FIELDS}
    data["revision"] = dossier.revision if dossier else 1
    return data


def _response(record, user, school, *, own=False):
    scope = scoped_cycle_ids(user, school) if own else None
    appointments = SchoolAppointment.objects.filter(
        school=school, staff=record,
    ).order_by("function_code", "cycle_code", "starts_on")
    assignments = StaffAssignment.objects.filter(
        school=school, staff=record,
    ).select_related("year", "classroom__level__cycle").order_by(
        "-year__start_date", "classroom__name", "duty",
    )
    if scope is not None:
        # Le salarié peut voir sa propre fiche, pas obtenir un panorama
        # de cycles qui ne sont pas autorisés à son compte.
        keys = profile_cycle_keys(school, scope)
        appointments = appointments.filter(cycle_code__in=keys)
        assignments = assignments.filter(classroom__level__cycle_id__in=scope)

    dossier = StaffProfessionalDossier.objects.filter(staff=record).first()
    portrait = StaffPhoto.objects.filter(staff=record).first()
    payload = {
        "staff": {
            "id": str(record.pk), "staff_code": record.staff_code,
            "first_name": record.first_name, "last_name": record.last_name,
            "position": record.position,
            "hired_on": record.hired_on.isoformat() if record.hired_on else None,
            "active": record.active, "has_account": bool(record.account_id),
            "photo_url": portrait_url(school.pk, record.pk, portrait, own=own),
        },
        "professional": _professional(dossier),
        "functions": [{
            "id": str(appt.pk), "code": appt.function_code,
            "label": function_label(school, appt.function_code),
            "cycle": appt.cycle_code,
            "cycle_label": CYCLE_LABELS.get(appt.cycle_code, appt.cycle_code)
                if appt.cycle_code else "Établissement entier",
            "starts_on": appt.starts_on.isoformat() if appt.starts_on else None,
            "ends_on": appt.ends_on.isoformat() if appt.ends_on else None,
            "active": appt.active, "effective": appt.is_effective,
        } for appt in appointments[:100]],
        "class_assignments": [{
            "id": str(row.pk), "year": row.year.name,
            "classroom": row.classroom.name,
            "cycle": row.classroom.level.cycle.name,
            "duty": row.duty, "active": row.active,
        } for row in assignments[:200]],
        "can_edit": (
            not own and has_permission(user, school, "school.staff.dossier.read")
            and has_permission(user, school, "school.staff.dossier.manage")
        ),
        "is_own_dossier": own,
        "can_edit_contact": own,
        "notice": "Dossier professionnel, distinct du dossier RH confidentiel.",
    }
    return JsonResponse(payload, headers={"Cache-Control": "no-store"})


@require_http_methods(["GET", "PATCH"])
@authorized
def staff_dossier(request, school_id, staff_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.staff.dossier.read"):
        return refuse()
    if scoped_cycle_ids(request.user, school) is not None:
        return refuse()
    record = StaffRecord.objects.filter(school=school, pk=staff_id).first()
    if record is None:
        return JsonResponse({"error": "Fiche du personnel introuvable."}, status=404)

    if request.method == "GET":
        return _response(record, request.user, school)
    if not has_permission(request.user, school, "school.staff.dossier.manage"):
        return refuse()

    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) - set(FIELDS) - {"revision"} or not set(data).intersection(FIELDS):
        return JsonResponse({"error": "Champs du dossier invalides ou absents."}, status=422)
    if type(data.get("revision")) is not int or data["revision"] < 1:
        return JsonResponse({"error": "Révision du dossier obligatoire."}, status=422)

    updated = {}
    for field in FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str) or len(value.strip()) > LIMITS[field]:
            return JsonResponse({"error": "Valeur professionnelle invalide."}, status=422)
        value = value.strip()
        if field == "professional_phone" and value and not re.fullmatch(
            r"[+0-9(). -]{5,45}", value
        ):
            return JsonResponse({"error": "Téléphone professionnel invalide."}, status=422)
        updated[field] = value

    try:
        with transaction.atomic():
            locked = StaffRecord.objects.select_for_update().filter(
                school=school, pk=record.pk
            ).first()
            if locked is None:
                return JsonResponse({"error": "Fiche du personnel introuvable."}, status=404)
            dossier, _ = StaffProfessionalDossier.objects.select_for_update().get_or_create(
                staff=locked
            )
            if dossier.revision != data["revision"]:
                return JsonResponse({
                    "error": "Dossier modifié par une autre personne.",
                    "revision": dossier.revision,
                }, status=409)
            for key, value in updated.items():
                setattr(dossier, key, value)
            dossier.full_clean()
            dossier.revision += 1
            dossier.save()
            log_event(school, request, "staff_dossier_updated", record.pk, {
                "fields": sorted(updated), "revision": dossier.revision,
            })
    except ValidationError:
        return JsonResponse({"error": "Une valeur du dossier est invalide."}, status=422)
    return _response(record, request.user, school)


@require_http_methods(["GET", "PATCH"])
@authorized
def my_staff_dossier(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    record = StaffRecord.objects.filter(
        school=school, account=request.user, active=True,
    ).first()
    if record is None:
        return JsonResponse({"error": "Aucune fiche de personnel liée à ce compte."}, status=404)
    if request.method == "PATCH":
        data, error = parse_body(request)
        if error is not None:
            return error
        allowed = {"professional_email", "professional_phone"}
        if set(data) - allowed - {"revision"} or not set(data).intersection(allowed):
            return JsonResponse({"error": "Seules vos coordonnées professionnelles sont modifiables."}, status=422)
        if type(data.get("revision")) is not int or data["revision"] < 1:
            return JsonResponse({"error": "Révision du dossier obligatoire."}, status=422)
        updated = {}
        for field in allowed.intersection(data):
            value = data[field]
            if not isinstance(value, str) or len(value.strip()) > LIMITS[field]:
                return JsonResponse({"error": "Coordonnée professionnelle invalide."}, status=422)
            value = value.strip()
            if field == "professional_phone" and value and not re.fullmatch(r"[+0-9(). -]{5,45}", value):
                return JsonResponse({"error": "Téléphone professionnel invalide."}, status=422)
            updated[field] = value
        with transaction.atomic():
            locked = StaffRecord.objects.select_for_update().get(pk=record.pk, school=school, account=request.user)
            dossier, _ = StaffProfessionalDossier.objects.select_for_update().get_or_create(staff=locked)
            if dossier.revision != data["revision"]:
                return JsonResponse({"error": "Dossier modifié depuis un autre écran.", "revision": dossier.revision}, status=409)
            for key, value in updated.items():
                setattr(dossier, key, value)
            try:
                dossier.full_clean()
            except ValidationError:
                return JsonResponse({"error": "Coordonnée invalide."}, status=422)
            dossier.revision += 1
            dossier.save()
            log_event(school, request, "staff_contact_updated", record.pk, {
                "fields": sorted(updated), "revision": dossier.revision,
            })
    return _response(record, request.user, school, own=True)
