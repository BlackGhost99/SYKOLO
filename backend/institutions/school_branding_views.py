"""Identite des etablissements : images isolees, sans modifier le branding YEM."""
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.views import authorized
from .models import SchoolBranding
from .services import has_permission, owns_school
from .views import access, log_event, parse_body

IMAGE_LIMITS = {"logo": 350_000, "banner": 900_000}
IMAGE_SIGNATURES = {
    "image/jpeg": lambda content: content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9"),
    "image/png": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in content[-24:],
}


def rejected(message, status=422):
    return JsonResponse({"error": message}, status=status)


def editable(user, school):
    return (owns_school(user, school) or
            has_permission(user, school, "school.settings.write"))


def output(school, record):
    revision = record.revision if record else 0
    base = f"/api/v1/schools/{school.pk}/branding"
    return {
        "school_id": str(school.pk),
        "name": school.name,
        "city": record.city if record else "",
        "tagline": record.tagline if record else "",
        "revision": revision,
        "logo_url": f"{base}/logo?v={revision}" if record and record.logo_data else None,
        "banner_url": f"{base}/banner?v={revision}" if record and record.banner_data else None,
    }


def revision_value(raw):
    if type(raw) is int and raw >= 0:
        return raw
    if isinstance(raw, str) and raw.isascii() and raw.isdigit():
        return int(raw) if len(raw) <= 10 else -1
    return -1


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def school_branding(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        return JsonResponse(output(school, SchoolBranding.objects.filter(school=school).first()))
    if not editable(request.user, school):
        return rejected("Droits insuffisants pour changer l'identite de l'etablissement.", 403)
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"revision", "city", "tagline"}:
        return rejected("Version, ville et devise sont requises.")
    revision = revision_value(data["revision"])
    city, tagline = data["city"], data["tagline"]
    if (revision < 0 or not isinstance(city, str) or not isinstance(tagline, str)
            or len(city.strip()) > 120 or len(tagline.strip()) > 160):
        return rejected("Valeurs invalides (ville : 120, devise : 160 caracteres).")
    with transaction.atomic():
        # Lock parent to serialize the first creation and avoid duplicate branding rows.
        type(school).objects.select_for_update().get(pk=school.pk)
        record = SchoolBranding.objects.select_for_update().filter(school=school).first()
        if (record.revision if record else 0) != revision:
            return rejected("L'identite a change. Rechargez les informations.", 409)
        if record is None:
            record = SchoolBranding(school=school, revision=0)
        record.city = city.strip()
        record.tagline = tagline.strip()
        record.revision += 1
        record.save()
        log_event(school, request, "school_branding_text_updated")
    return JsonResponse(output(school, record))


@never_cache
@require_http_methods(["GET", "POST", "DELETE"])
@authorized
def school_brand_image(request, school_id, kind):
    if kind not in IMAGE_LIMITS:
        return rejected("Type d'image inconnu.", 404)
    school, error = access(request, school_id)
    if error is not None:
        return error
    data_field, mime_field = kind+"_data", kind+"_content_type"
    if request.method == "GET":
        record = SchoolBranding.objects.filter(school=school).first()
        if not record or not getattr(record, data_field):
            return rejected("Image non configuree pour cet etablissement.", 404)
        response = HttpResponse(bytes(getattr(record, data_field)), content_type=getattr(record, mime_field))
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
    if not editable(request.user, school):
        return rejected("Droits insuffisants pour changer cette image.", 403)
    if request.method == "POST":
        try:
            revision = revision_value(request.POST.get("revision"))
            upload = request.FILES.get("image")
        except (ValueError, TypeError):
            return rejected("Fichier invalide.")
        if (revision < 0 or upload is None or upload.content_type not in IMAGE_SIGNATURES or
                upload.size < 16 or upload.size > IMAGE_LIMITS[kind]):
            return rejected("Image JPG/PNG attendue (logo 350 Ko, banniere 900 Ko maximum).")
        payload = upload.read(IMAGE_LIMITS[kind]+1)
        if len(payload) != upload.size or not IMAGE_SIGNATURES[upload.content_type](payload):
            return rejected("Image corrompue ou format invalide.")
    else:
        data, error = parse_body(request)
        if error is not None:
            return error
        if set(data) != {"revision"}:
            return rejected("Version du document requise.")
        revision = revision_value(data["revision"])
        if revision < 0:
            return rejected("Version invalide.")
    with transaction.atomic():
        type(school).objects.select_for_update().get(pk=school.pk)
        record = SchoolBranding.objects.select_for_update().filter(school=school).first()
        if (record.revision if record else 0) != revision:
            return rejected("Le visuel a change. Rechargez la page.", 409)
        if record is None:
            record = SchoolBranding(school=school, revision=0)
        setattr(record, data_field, payload if request.method == "POST" else None)
        setattr(record, mime_field, upload.content_type if request.method == "POST" else "")
        record.revision += 1
        record.save()
        log_event(school, request, "school_branding_image_changed", kind, {
            "action": "upload" if request.method == "POST" else "remove",
        })
    return JsonResponse(output(school, record))
