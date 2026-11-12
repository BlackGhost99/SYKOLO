"""Private parent child profiles, school-scoped forms and reviewed application uploads.

Never infer a school/student access grant from ownership of a pre-admission profile.
Submitted answers remain an application snapshot. Staff decide and verify evidence.
"""
import base64
import binascii
import re
from datetime import date
from uuid import UUID

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.views import authorized
from .academic_models import AcademicClass
from .admission_models import AdmissionDocument, AdmissionEvent
from .admission_policy import DOCUMENT_CODE, ROUTES, effective_policy, required_for_route
from .enrollment_form import BASE_FIELDS, load_config
from .parent_admission_models import (
    FamilyChild, FamilyChildPhoto, ParentAdmissionRequest, ParentDocumentUpload,
)
from .services import has_permission
from .views import access, log_event, parse_body

PHOTO_MAX_BYTES = 350_000
DOCUMENT_MAX_BYTES = 2_000_000
PROFILE_LIMITS = {
    "gender": 1, "place_of_birth": 120, "nationality": 80,
    "address": 255, "previous_school": 180,
}
IMAGE_PREFIXES = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}
DOCUMENT_MIMES = {**IMAGE_PREFIXES, "application/pdf": b"%PDF-"}


def problem(message, status=422):
    return JsonResponse({"error": message}, status=status)


def safe_text(value, maximum):
    if not isinstance(value, str) or len(value.strip()) > maximum or any(ord(ch) < 32 for ch in value):
        raise ValueError("Texte invalide ou trop long.")
    return value.strip()


def clean_profile(raw):
    if not isinstance(raw, dict) or set(raw) - PROFILE_LIMITS.keys():
        raise ValueError("Informations de profil invalides.")
    values = {key: safe_text(value, PROFILE_LIMITS[key]) for key, value in raw.items()}
    if values.get("gender") not in ("", None, "M", "F"):
        raise ValueError("Sexe invalide.")
    return values


def clean_date(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("Date de naissance invalide.")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Date de naissance invalide.") from None
    if result > date.today():
        raise ValueError("La date de naissance est dans le futur.")
    return result


def child_output(child):
    return {
        "id": str(child.pk),
        "first_name": child.first_name, "last_name": child.last_name,
        "date_of_birth": child.date_of_birth.isoformat() if child.date_of_birth else None,
        "profile": child.profile, "revision": child.revision,
        "photo_url": f"/api/v1/parents/family-children/{child.pk}/photo"
            if FamilyChildPhoto.objects.filter(child_id=child.pk).exists() else None,
    }


def public_form_payload(school, year, level, route):
    config, revision = load_config(school)
    fields = []
    for key, label, section, visible_default, required_default in BASE_FIELDS:
        if key == "guardian_phone":
            continue  # existing guardian contact field on the application form
        rule = config.get("fields", {}).get(key, {"visible": visible_default, "required": required_default})
        if not rule.get("visible", visible_default):
            continue
        fields.append({
            "key": key, "label": label, "section": section,
            "type": "date" if key == "date_of_birth" else "select" if key == "gender" else "text",
            "options": ["F", "M"] if key == "gender" else [],
            "required": bool(rule.get("required", required_default)),
            "max_length": PROFILE_LIMITS.get(key, 254 if key == "guardian_email" else 120),
        })
    policy = effective_policy(school, year, level)
    configured = config.get("documents", [])
    documents = [{
        "key": d["key"], "label": d["label"], "required": bool(d["required"]),
    } for d in configured]
    known = {item["key"] for item in documents}
    route_docs = required_for_route(route, policy)
    for key in route_docs:
        if key not in known:
            documents.append({"key": key, "label": key.replace("_", " ").replace("-", " ").capitalize(),
                              "required": True})
            known.add(key)
        else:
            next(d for d in documents if d["key"] == key)["required"] = True
    return {
        "revision": revision,
        "fields": fields, "custom_fields": config.get("custom_fields", []),
        "documents": documents,
    }


@never_cache
@require_GET
@authorized
def school_form(request):
    classroom_id = request.GET.get("classroom", "")
    route = request.GET.get("route", "direct")
    try:
        classroom_id = UUID(classroom_id)
    except (TypeError, ValueError):
        return problem("Classe invalide.")
    if route not in ROUTES:
        return problem("Voie d'admission invalide.")
    row = AcademicClass.objects.select_related("school", "year", "level").filter(
        pk=classroom_id, active=True, school__is_active=True, year__active=True,
        level__active=True, level__cycle__active=True,
        school__public_listing__published=True,
    ).first()
    if not row:
        return problem("Classe indisponible.", 404)
    policy = effective_policy(row.school, row.year, row.level)
    if policy and route not in policy.enabled_routes:
        return problem("Cette voie d'admission est fermée.", 409)
    form = public_form_payload(row.school, row.year, row.level, route)
    return JsonResponse({
        "school_id": str(row.school_id), "school_name": row.school.name,
        "classroom_id": str(row.pk), "route": route, **form,
    })


@never_cache
@require_http_methods(["GET", "PUT"])
@authorized
def family_profile(request, child_id):
    if request.method == "GET":
        child = FamilyChild.objects.filter(pk=child_id, owner=request.user, active=True).first()
        return JsonResponse(child_output(child)) if child else problem("Profil introuvable.", 404)
    data, failure = parse_body(request)
    if failure is not None:
        return failure
    if not isinstance(data, dict) or set(data) != {"first_name", "last_name", "date_of_birth", "profile", "revision"}:
        return problem("Champs du profil ou révision manquants.")
    try:
        first = safe_text(data["first_name"], 120)
        last = safe_text(data["last_name"], 120)
        if not first or not last or type(data["revision"]) is not int:
            raise ValueError("Nom, prénom et révision requis.")
        dob = clean_date(data["date_of_birth"])
        details = clean_profile(data["profile"])
    except ValueError as exc:
        return problem(str(exc))
    with transaction.atomic():
        child = FamilyChild.objects.select_for_update().filter(owner=request.user, pk=child_id, active=True).first()
        if child is None:
            return problem("Profil introuvable.", 404)
        if child.revision != data["revision"]:
            return problem("Ce profil a changé. Actualisez-le.", 409)
        child.first_name, child.last_name, child.date_of_birth, child.profile = first, last, dob, details
        child.revision += 1
        child.full_clean()
        child.save()
    return JsonResponse(child_output(child))


def photo_permission(request, child):
    if child.owner_id == request.user.pk:
        return True
    # Only staff who have an actual application in their school, and admission-read rights.
    schools = (ParentAdmissionRequest.objects.filter(child=child).values_list(
        "application__school_id", flat=True).distinct())
    for school_id in schools:
        school, failure = access(request, school_id)
        if failure is None and has_permission(request.user, school, "school.admissions.read"):
            return True
    return False


@never_cache
@require_http_methods(["GET", "POST", "DELETE"])
@authorized
def family_photo(request, child_id):
    child = FamilyChild.objects.filter(pk=child_id, active=True).first()
    if not child or not photo_permission(request, child):
        return problem("Photo introuvable.", 404)
    if request.method == "GET":
        item = FamilyChildPhoto.objects.filter(child=child).first()
        if not item:
            return problem("Photo introuvable.", 404)
        response = HttpResponse(bytes(item.data), content_type=item.content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
    if child.owner_id != request.user.pk:
        return problem("Seul le parent propriétaire du profil peut modifier cette photo.", 403)
    if request.method == "DELETE":
        FamilyChildPhoto.objects.filter(child=child).delete()
        return JsonResponse({"photo_url": None})
    body, failure = parse_body(request)
    if failure is not None:
        return failure
    data_url = body.get("photo") if isinstance(body, dict) and set(body) == {"photo"} else None
    if not isinstance(data_url, str) or len(data_url) > 500000:
        return problem("Photo invalide ou trop volumineuse.")
    match = re.fullmatch(r"data:(image/jpeg|image/png);base64,([A-Za-z0-9+/=]+)", data_url)
    if not match:
        return problem("Photo JPEG ou PNG uniquement.")
    mime, encoded = match.groups()
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return problem("Photo corrompue.")
    if len(content) > PHOTO_MAX_BYTES or not content.startswith(IMAGE_PREFIXES[mime]):
        return problem("Photo invalide ou trop volumineuse (350 Ko au maximum).")
    # No public storage, no data URL in the database, and no child portrait on the CDN.
    FamilyChildPhoto.objects.update_or_create(child=child,
        defaults={"data": content, "content_type": mime})
    return JsonResponse({"photo_url": f"/api/v1/parents/family-children/{child.pk}/photo"})


def document_output(item, link):
    upload = ParentDocumentUpload.objects.filter(document=item).first() if item else None
    return {
        "status": item.status if item else "missing",
        "review_reason": item.review_reason if item else "",
        "uploaded": bool(upload),
        "filename": upload.filename if upload else None,
        "download_url": f"/api/v1/parents/applications/{link.pk}/documents/{item.code}/file" if upload else None,
    }


@never_cache
@require_GET
@authorized
def parent_documents(request, request_id):
    link = ParentAdmissionRequest.objects.select_related("application").filter(
        pk=request_id, owner=request.user).first()
    if not link:
        return problem("Dossier introuvable.", 404)
    docs = {doc.code: doc for doc in AdmissionDocument.objects.filter(
        school=link.application.school, application=link.application)}
    expected = link.document_requirements or [
        {"key": code, "label": code.replace("_", " ").capitalize(), "required": True}
        for code in link.application.required_documents]
    return JsonResponse({"documents": [
        {**rule, **document_output(docs.get(rule["key"]), link)} for rule in expected
    ], "application_status": link.application.status})


def safe_upload(upload):
    if not upload or upload.size > DOCUMENT_MAX_BYTES or upload.size <= 0:
        raise ValueError("Document manquant ou trop volumineux (2 Mo maximum).")
    content = upload.read(DOCUMENT_MAX_BYTES + 1)
    if len(content) != upload.size or len(content) > DOCUMENT_MAX_BYTES:
        raise ValueError("Document trop volumineux.")
    mime = next((m for m, prefix in DOCUMENT_MIMES.items() if content.startswith(prefix)), None)
    if mime is None:
        raise ValueError("Formats autorisés : PDF, JPG et PNG uniquement.")
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", upload.name.rsplit("/", 1)[-1])[:120]
    if filename.startswith("."):
        filename = "justificatif_" + filename.lstrip(".")
    return content, mime, filename or "justificatif"


@never_cache
@require_http_methods(["POST"])
@authorized
def upload_parent_document(request, request_id, code):
    if not DOCUMENT_CODE.fullmatch(code):
        return problem("Code de document invalide.")
    try:
        content, mime, filename = safe_upload(request.FILES.get("file"))
    except ValueError as exc:
        return problem(str(exc))
    with transaction.atomic():
        link = ParentAdmissionRequest.objects.select_related("application").select_for_update().filter(
            pk=request_id, owner=request.user).first()
        if not link:
            return problem("Dossier introuvable.", 404)
        application = link.application
        if application.status not in ("submitted", "review"):
            return problem("Les documents ne peuvent plus être modifiés après décision.", 409)
        allowed = {d["key"] for d in link.document_requirements} or set(application.required_documents)
        if code not in allowed:
            return problem("Cette pièce n'est pas demandée par l'établissement.", 403)
        doc, _ = AdmissionDocument.objects.update_or_create(
            school=application.school, application=application, code=code,
            defaults={"reference": "Document transmis par le parent : " + filename[:120],
                      "status": "pending", "review_reason": "",
                      "reviewed_by": None, "reviewed_at": None})
        ParentDocumentUpload.objects.update_or_create(document=doc,
            defaults={"uploaded_by": request.user, "filename": filename,
                      "content_type": mime, "content": content, "size": len(content)})
        application.revision += 1
        application.save(update_fields=["revision"])
        AdmissionEvent.objects.create(school=application.school, application=application,
            previous_status=application.status, new_status=application.status,
            reason="Pièce déposée par un parent : " + code, actor=request.user)
        log_event(application.school, request, "parent_document_uploaded", doc.pk)
    return JsonResponse({"code": code, "status": "pending", "uploaded": True})


def secure_file(response_data, content_type, filename):
    # Always download attachments: never render a possibly malicious PDF in-app.
    response = HttpResponse(response_data, content_type=content_type)
    response["Content-Disposition"] = 'attachment; filename="' + filename + '"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["Cache-Control"] = "private, no-store"
    return response


@never_cache
@require_GET
@authorized
def parent_document_file(request, request_id, code):
    link = ParentAdmissionRequest.objects.filter(pk=request_id, owner=request.user).first()
    if not link:
        return problem("Dossier introuvable.", 404)
    upload = ParentDocumentUpload.objects.select_related("document").filter(
        document__application=link.application, document__code=code).first()
    if not upload:
        return problem("Document introuvable.", 404)
    return secure_file(bytes(upload.content), upload.content_type, upload.filename)


@never_cache
@require_GET
@authorized
def school_document_file(request, school_id, application_id, code):
    school, failure = access(request, school_id)
    if failure is not None:
        return failure
    if not has_permission(request.user, school, "school.admissions.read"):
        return problem("Accès refusé.", 403)
    upload = ParentDocumentUpload.objects.select_related("document").filter(
        document__school=school, document__application_id=application_id,
        document__code=code).first()
    if not upload:
        return problem("Document introuvable.", 404)
    return secure_file(bytes(upload.content), upload.content_type, upload.filename)
