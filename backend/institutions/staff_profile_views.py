"""Protected teacher profile and portrait endpoints: one StaffRecord, two UI surfaces."""
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.views import authorized
from .staff_models import StaffRecord
from .staff_profile_models import StaffProfile
from .services import has_permission
from .views import access, log_event, parse_body

PHOTO_MAX_BYTES = 350_000
PHOTO_SIGNATURES = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}


def failure(message, status=422):
    return JsonResponse({"error": message}, status=status)


def own_staff(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return None, None, error
    staff = StaffRecord.objects.filter(
        school=school, account=request.user, active=True,
    ).first()
    if staff is None:
        return school, None, failure("Aucune fiche Personnel active liée à ce compte.", 404)
    return school, staff, None


def profile_output(staff, profile):
    return {
        "staff_id": str(staff.pk),
        "first_name": staff.first_name,
        "last_name": staff.last_name,
        "staff_code": staff.staff_code,
        "position": staff.position,
        "presentation": profile.presentation if profile else "",
        "revision": profile.revision if profile else 1,
        "photo_url": (f"/api/v1/schools/{staff.school_id}/staff/{staff.pk}/photo"
                      if profile and profile.photo_data else None),
    }


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def my_profile(request, school_id):
    school, staff, error = own_staff(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        profile = StaffProfile.objects.filter(staff=staff).first()
        return JsonResponse(profile_output(staff, profile))
    body, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(body, dict) or set(body) != {"revision", "presentation"}:
        return failure("Seule la présentation du profil est modifiable.")
    if type(body["revision"]) is not int or body["revision"] < 1:
        return failure("Révision invalide.")
    value = body["presentation"]
    if not isinstance(value, str) or len(value.strip()) > 280:
        return failure("Présentation invalide (280 caractères maximum).")
    with transaction.atomic():
        locked_staff = StaffRecord.objects.select_for_update().filter(
            pk=staff.pk, school=school, account=request.user, active=True,
        ).first()
        if locked_staff is None:
            return failure("Fiche Personnel inaccessible.", 404)
        profile, _ = StaffProfile.objects.get_or_create(staff=locked_staff)
        if profile.revision != body["revision"]:
            return failure("Conflit de version : rechargez votre profil.", 409)
        profile.presentation = value.strip()
        profile.revision += 1
        profile.save(update_fields=["presentation", "revision", "updated_at"])
        log_event(school, request, "staff_profile_updated", staff.pk)
    return JsonResponse(profile_output(staff, profile))


@never_cache
@require_http_methods(["GET", "POST", "DELETE"])
@authorized
def staff_photo(request, school_id, staff_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    staff = StaffRecord.objects.filter(school=school, pk=staff_id, active=True).first()
    if staff is None:
        return failure("Photo introuvable.", 404)
    owner = staff.account_id == request.user.pk
    can_read = owner or has_permission(request.user, school, "school.staff.read") or (
        has_permission(request.user, school, "school.staff.dossier.read")
    )
    if request.method == "GET":
        if not can_read:
            return failure("Photo introuvable.", 404)
        profile = StaffProfile.objects.filter(staff=staff).first()
        if not profile or not profile.photo_data:
            return failure("Photo introuvable.", 404)
        response = HttpResponse(bytes(profile.photo_data), content_type=profile.photo_content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
    if not owner:
        return failure("Seul le propriétaire du profil peut changer sa photo.", 403)
    if request.method == "POST":
        upload = request.FILES.get("photo")
        if not upload or upload.content_type not in PHOTO_SIGNATURES or upload.size > PHOTO_MAX_BYTES or upload.size < 8:
            return failure("Photo JPEG/PNG requise, de 350 Ko maximum.")
        payload = upload.read(PHOTO_MAX_BYTES + 1)
        if len(payload) != upload.size or not payload.startswith(PHOTO_SIGNATURES[upload.content_type]):
            return failure("Photo corrompue ou non conforme.")
    with transaction.atomic():
        locked_staff = StaffRecord.objects.select_for_update().filter(
            school=school, pk=staff_id, account=request.user, active=True,
        ).first()
        if locked_staff is None:
            return failure("Accès refusé.", 403)
        profile, _ = StaffProfile.objects.get_or_create(staff=locked_staff)
        if request.method == "DELETE":
            profile.photo_data = None
            profile.photo_content_type = ""
        else:
            profile.photo_data = payload
            profile.photo_content_type = upload.content_type
        profile.revision += 1
        profile.save(update_fields=["photo_data", "photo_content_type", "revision", "updated_at"])
        log_event(school, request, "staff_photo_changed", staff.pk)
    return JsonResponse(profile_output(staff, profile))
