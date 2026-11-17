"""Authenticated downloads. No public URLs, inline render, or external fetching."""
import hashlib
from pathlib import PurePath
from uuid import UUID
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from accounts.views import authorized
from .academic_models import AcademicYear
from .diary_resource_models import DiaryResource
from .models import School
from .parent_views import child_scope
from .services import has_permission
from .teaching_diary_models import TeachingDiaryEntry
from .teaching_diary_views import school_courses, writable, error, family_entries
from .views import access, log_event, refuse, parse_body

MAX_BYTES = 1048576
SCHOOL_BUDGET = 20 * 1048576


def payload(upload):
    if not upload or not 1 <= upload.size <= MAX_BYTES:
        raise ValueError("Fichier requis, 1 Mio maximum.")
    filename = PurePath(upload.name.replace("\\", "/")).name
    if not filename or len(filename)>160 or any(ord(c)<32 or ord(c)==127 for c in filename):
        raise ValueError("Nom de fichier invalide.")
    raw = upload.read(MAX_BYTES+1)
    if len(raw)!=upload.size:
        raise ValueError("Fichier incomplet.")
    ext = PurePath(filename).suffix.lower()
    # Until an antimalware service is connected, restrict file types to text.
    # Strict UTF-8, no controls other than line separators and tabs.
    if ext != ".txt":
        raise ValueError("Seuls les documents texte UTF-8 (.txt) sont activés. PDF et autres formats nécessitent la validation antivirus.")
    try:
        value = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Le fichier texte doit être encodé en UTF-8.") from None
    if not value.strip() or any((ord(c)<32 and c not in "\r\n\t") or ord(c)==127 for c in value):
        raise ValueError("Contenu texte invalide.")
    raw = value.encode("utf-8")
    if not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("Taille invalide.")
    return filename, raw


def metadata(resource):
    return {"id":str(resource.pk), "filename":resource.filename, "size":resource.size}


def download(row):
    response = HttpResponse(bytes(row.data), content_type="application/octet-stream")
    response["Content-Disposition"] = content_disposition_header(True, row.filename)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def school_entry(request, school_id, entry_id):
    school, denied = access(request, school_id)
    if denied is not None:
        return None, None, denied
    if not has_permission(request.user,school,"school.curriculum.read"):
        return None,None,refuse()
    entry=TeachingDiaryEntry.objects.filter(pk=entry_id,course__in=school_courses(request.user,school)).select_related("course__year","course__classroom__level__cycle","course__subject").first()
    if entry is None:
        return None,None,error("Séance introuvable ou non autorisée.",404)
    return school,entry,None


@never_cache
@require_http_methods(["GET","POST"])
@authorized
def resources(request,school_id,entry_id):
    school,entry,denied=school_entry(request,school_id,entry_id)
    if denied is not None:
        return denied
    if request.method=="GET":
        return JsonResponse({"resources":[metadata(r) for r in entry.resources.filter(active=True).defer("data").order_by("created_at","pk")],"writable":writable(entry.course)})
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0)>MAX_BYTES+8192:
            return error("Requête trop volumineuse.",413)
        if set(request.FILES)!={"file"} or len(request.FILES.getlist("file"))!=1 or set(request.POST)!={"id"} or len(request.POST.getlist("id"))!=1:
            return error("Un fichier et son identifiant sont requis.")
        if request.FILES["file"].size>MAX_BYTES:
            return error("Fichier trop volumineux.",413)
        key=UUID(request.POST["id"])
        filename,raw=payload(request.FILES["file"])
        digest=hashlib.sha256(raw).hexdigest()
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            _,entry,denied=school_entry(request,school_id,entry_id)
            if denied is not None:return denied
            entry.course.year=AcademicYear.objects.select_for_update().get(pk=entry.course.year_id)
            if not writable(entry.course):return error("Année ou cours non modifiable.",409)
            existing=DiaryResource.objects.filter(pk=key,entry=entry).defer("data").first()
            if existing:
                if existing.active and existing.uploader_id==request.user.pk and existing.digest==digest and existing.filename==filename:
                    return JsonResponse(metadata(existing))
                return error("Identifiant déjà utilisé.",409)
            if entry.resources.count()>=5:return error("Maximum de cinq documents par séance, y compris les archives.",409)
            total=DiaryResource.objects.filter(entry__course__school=school).aggregate(total=Sum("size"))["total"] or 0
            if total+len(raw)>SCHOOL_BUDGET:return error("Quota initial de stockage atteint.",409)
            row=DiaryResource.objects.create(pk=key,entry=entry,filename=filename,content_type="text/plain",size=len(raw),digest=digest,data=raw,uploader=request.user)
            log_event(school,request,"diary_resource_uploaded",row.pk)
            return JsonResponse(metadata(row),status=201)
    except (ValueError,TypeError):
        return error("Fichier texte UTF-8 (.txt) valide requis, 1 Mio maximum.")
    except IntegrityError:
        return error("Opération concurrente.",409)


@never_cache
@require_http_methods(["GET","PATCH"])
@authorized
def resource_detail(request,school_id,entry_id,resource_id):
    school,entry,denied=school_entry(request,school_id,entry_id)
    if denied is not None:return denied
    if request.method=="GET":
        row=entry.resources.filter(pk=resource_id,active=True).first()
        return download(row) if row else error("Document introuvable.",404)
    body, denied = parse_body(request)
    if denied is not None: return denied
    if body != {}: return error("Retrait du document : objet JSON vide requis.")
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        _,entry,denied=school_entry(request,school_id,entry_id)
        if denied is not None:return denied
        entry.course.year=AcademicYear.objects.select_for_update().get(pk=entry.course.year_id)
        if not writable(entry.course):return error("Année ou cours non modifiable.",409)
        row=entry.resources.filter(pk=resource_id).defer("data").first()
        if not row:return error("Document introuvable.",404)
        if row.active:
            row.active=False
            row.revoked_at=timezone.now()
            row.save(update_fields=["active","revoked_at"])
            log_event(school,request,"diary_resource_revoked",row.pk)
        return JsonResponse({"revoked":True})


@never_cache
@require_GET
@authorized
def child_resource(request,student_id,resource_id):
    student,year_id,denied=child_scope(request,student_id)
    if denied is not None:return denied
    row=DiaryResource.objects.filter(pk=resource_id,active=True,entry__in=family_entries(student,year_id)).first()
    return download(row) if row else error("Document introuvable.",404)
