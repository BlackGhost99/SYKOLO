"""Portrait du personnel : une seule image privée pour professeur et administration."""
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.views import authorized
from .cycle_scope import scoped_cycle_ids
from .services import has_permission
from .staff_models import StaffPhoto, StaffRecord
from .views import access, log_event, refuse

MAX_PHOTO_BYTES = 350_000
SIGNATURES = {
    "image/jpeg": b"\xff\xd8\\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def portrait_url(school_id, staff_id, photo, *, own=False):
    if photo is None:
        return None
    endpoint = "me" if own else str(staff_id)
    return f"/api/v1/schools/{school_id}/staff/{endpoint}/photo?v={photo.revision}"


def valid_photo(upload, data):
    if not upload or not 0 < len(data) <= MAX_PHOTO_BYTES:
        return False
    mime = upload.content_type
    if mime not in SIGNATURES or not data.startswith(SIGNATURES[mime]):
        return False
    if mime == "image/png":
        return len(data) >= 33 and data[12:16] == b"IHDR" and (
            int.from_bytes(data[16:20], "big") > 0 and
            int.from_bytes(data[20:24], "big") > 0
        )
    return data.endswith(b"\xff\xd9")


@never_cache
@require_http_methods(["GET", "POST", "DELETE"])
@authorized
def staff_photo(request, school_id, staff_id=None):
    school, error = access(request, school_id)
    if error is not None:
        return error
    own = staff_id is None
    if own:
        record = StaffRecord.objects.filter(
            school=school, account=request.user, active=True,
        ).first()
    else:
        if scoped_cycle_ids(request.user, school) is not None:
            return refuse()
        if not (
            has_permission(request.user, school, "school.staff.read")
            or has_permission(request.user, school, "school.staff.dossier.read")
        ):
            return refuse()
        record = StaffRecord.objects.filter(school=school, pk=staff_id).first()
    if record is None:
        return JsonResponse({"error": "Personnel introuvable."}, status=404)

    if request.method == "GET":
        photo = StaffPhoto.objects.filter(staff=record).first()
        if photo is None:
            return JsonResponse({"error": "Aucune photo de profil."}, status=404)
        response = HttpResponse(bytes(photo.data), content_type=photo.content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response

    if not own and not has_permission(request.user, school, "school.staff.dossier.manage"):
        return refuse()
    if request.method == "DELETE":
        with transaction.atomic():
            deleted, _ = StaffPhoto.objects.filter(staff=record).delete()
            if deleted:
                log_event(school, request, "staff_photo_deleted", record.pk)
        return JsonResponse({"photo_url": None}, headers={"Cache-Control": "no-store"})

    upload = request.FILES.get("photo")
    if upload is None or upload.size <= 0 or upload.size > MAX_PHOTO_BYTES:
        return JsonResponse({
            "error": "Photo JPEG ou PNG requise (350 Ko maximum).",
        }, status=422)
    data = upload.read(MAX_PHOTO_BYTES + 1)
    if not valid_photo(upload, data):
        return JsonResponse({"error": "Photo JPEG ou PNG invalide."}, status=422)
    with transaction.atomic():
        record = StaffRecord.objects.select_for_update().get(pk=record.pk, school=school)
        photo, created = StaffPhoto.objects.select_for_update().get_or_create(
            staff=record, defaults={"data": data, "content_type": upload.content_type},
        )
        if not created:
            photo.data = data
            photo.content_type = upload.content_type
            photo.revision += 1
            photo.save(update_fields=["data", "content_type", "revision", "updated_at"])
        log_event(school, request, "staff_photo_updated", record.pk, {
            "photo_revision": photo.revision,
        })
    return JsonResponse({
        "photo_url": portrait_url(school.pk, record.pk, photo, own=own),
    }, headers={"Cache-Control": "no-store"})
