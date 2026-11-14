"""Parents deja scolarises: recherche d'ecole et demandes sans acces aux dossiers.

La demande ne recherche pas un eleve et ne cree pas d'inscription. L'ouverture
des donnees reste reservee a GuardianAccountLink, apres verification humaine.
"""
from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.views import authorized
from .models import School
from .parent_existing_models import ExistingStudentLinkRequest as LinkRequest
from .services import has_permission
from .views import access, log_event, parse_body, refuse


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def normalized(value, max_length, required=False):
    if not isinstance(value, str):
        raise ValueError("Informations invalides.")
    text = " ".join(value.split())
    if (required and not text) or len(text) > max_length or any(ord(c) < 32 for c in text):
        raise ValueError("Informations invalides ou trop longues.")
    return text


def summary(row):
    return {
        "id": str(row.pk), "school": str(row.school_id), "school_name": row.school.name,
        "first_name": row.first_name, "last_name": row.last_name, "student_code": row.student_code,
        "status": row.status, "created_at": row.created_at.isoformat(),
    }


def staff_summary(row):
    return {
        **summary(row), "username": row.owner.get_username(),
        "guardian_name": row.guardian_name, "contact_phone": row.contact_phone,
    }


@never_cache
@require_GET
@authorized
def school_directory(request):
    """Recherche minimale des etablissements ACTIFS, meme sans places publiees."""
    q = request.GET.get("q", "").strip()
    if len(q) > 80:
        return fail("Recherche trop longue.")
    if q and len(q) < 2:
        return JsonResponse({"schools": []})
    rows = School.objects.filter(is_active=True)
    if q:
        rows = rows.filter(Q(name__icontains=q) | Q(short_name__icontains=q))
    rows = rows.order_by("name", "pk")[:60]
    return JsonResponse({"schools": [
        {"id": str(row.pk), "name": row.name, "school_type": row.school_type}
        for row in rows
    ]})


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def family_requests(request):
    if request.method == "GET":
        rows = LinkRequest.objects.select_related("school").filter(
            owner=request.user
        ).order_by("-created_at", "-pk")[:100]
        return JsonResponse({"requests": [summary(row) for row in rows]})

    data, error = parse_body(request)
    if error is not None:
        return error
    expected = {"school", "first_name", "last_name", "student_code", "guardian_name", "contact_phone"}
    if set(data) != expected:
        return fail("École, enfant et responsable légal requis.")
    try:
        school_id = UUID(data["school"]) if isinstance(data["school"], str) else None
        first = normalized(data["first_name"], 120, required=True)
        last = normalized(data["last_name"], 120, required=True)
        code = normalized(data["student_code"], 50)
        guardian = normalized(data["guardian_name"], 180, required=True)
        phone = normalized(data["contact_phone"], 45)
    except (ValueError, TypeError, AttributeError):
        return fail("Informations invalides ou incomplètes.")
    if not school_id:
        return fail("Établissement invalide.")

    with transaction.atomic():
        school = School.objects.select_for_update().filter(pk=school_id, is_active=True).first()
        if school is None:
            return fail("Établissement indisponible.", 404)
        previous = LinkRequest.objects.filter(
            owner=request.user, school=school, status=LinkRequest.PENDING,
            first_name__iexact=first, last_name__iexact=last, student_code__iexact=code,
        ).order_by("-created_at").first()
        if previous:
            # N'atteste ni l'existence de l'eleve ni celle du responsable legal.
            return JsonResponse(summary(previous), status=200)
        if LinkRequest.objects.filter(owner=request.user, school=school, status=LinkRequest.PENDING).count() >= 5:
            return fail("Vous avez déjà cinq demandes à traiter dans cet établissement.", 429)
        recent = timezone.now() - timedelta(days=7)
        if LinkRequest.objects.filter(owner=request.user, created_at__gte=recent).count() >= 15:
            return fail("Limite de demandes atteinte. Contactez l'établissement.", 429)
        row = LinkRequest.objects.create(
            school=school, owner=request.user, first_name=first, last_name=last,
            student_code=code, guardian_name=guardian, contact_phone=phone,
        )
        log_event(school, request, "parent_link_requested", row.pk)
    return JsonResponse(summary(row), status=201)


@never_cache
@require_http_methods(["PATCH"])
@authorized
def family_request_detail(request, request_id):
    data, error = parse_body(request)
    if error is not None:
        return error
    if data != {"status": "cancelled"}:
        return fail("Seule l'annulation d'une demande est autorisée.")
    with transaction.atomic():
        row = LinkRequest.objects.select_for_update().filter(
            pk=request_id, owner=request.user
        ).first()
        if row is None:
            return fail("Demande introuvable.", 404)
        if row.status != LinkRequest.PENDING:
            return fail("Cette demande a déjà été traitée.", 409)
        row.status = LinkRequest.CANCELLED
        row.save(update_fields=["status"])
        log_event(row.school, request, "parent_link_cancelled", row.pk)
    return JsonResponse(summary(row))


def staff_access(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, "school.parents.manage"):
        return None, refuse()
    return school, None


@never_cache
@require_GET
@authorized
def school_requests(request, school_id):
    school, error = staff_access(request, school_id)
    if error is not None:
        return error
    rows = LinkRequest.objects.select_related("school", "owner").filter(
        school=school, status=LinkRequest.PENDING
    ).order_by("created_at", "pk")[:250]
    return JsonResponse({"requests": [staff_summary(row) for row in rows]})


@never_cache
@require_http_methods(["PATCH"])
@authorized
def school_request_detail(request, school_id, request_id):
    school, error = staff_access(request, school_id)
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if data != {"status": "rejected"}:
        return fail("Seul le refus administratif est autorisé sur cette route.")
    with transaction.atomic():
        row = LinkRequest.objects.select_for_update().filter(
            school=school, pk=request_id
        ).first()
        if row is None:
            return fail("Demande introuvable.", 404)
        if row.status != LinkRequest.PENDING:
            return fail("Demande déjà traitée.", 409)
        row.status = LinkRequest.REJECTED
        row.reviewed_by = request.user
        row.reviewed_at = timezone.now()
        row.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        log_event(school, request, "parent_link_rejected", row.pk)
    return JsonResponse(staff_summary(row))
