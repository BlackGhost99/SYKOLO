"""A destination-bound authorization to reuse a YEM identity."""
from uuid import UUID

from django.core import signing
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.views import authorized

from .models import School
from .services import has_permission
from .student_models import Student
from .views import access, log_event, parse_body, refuse

SALT = "yem.student-transfer.v1"
MAX_AGE = 7 * 24 * 60 * 60


@never_cache
@require_POST
@authorized
def issue(request, school_id, student_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not all(has_permission(request.user, school, permission) for permission in (
        "school.students.manage", "school.admissions.decide",
    )):
        return refuse()
    body, error = parse_body(request)
    if error is not None:
        return error
    try:
        destination = UUID(body["destination"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return JsonResponse({"error": "Code de l’école de destination invalide."}, status=422)
    if destination == school.pk or not School.objects.filter(pk=destination, is_active=True).exists():
        return JsonResponse({"error": "École de destination invalide."}, status=422)
    with transaction.atomic():
        student = Student.objects.filter(pk=student_id, school=school).first()
        if student is None:
            return JsonResponse({"error": "Élève introuvable."}, status=404)
        code = signing.dumps({"student": str(student.pk), "destination": str(destination)}, salt=SALT)
        log_event(school, request, "student_transfer_issued", student.pk, {"destination": str(destination)})
    return JsonResponse({"transfer_code": code, "valid_days": 7}, status=201)


def transfer_identity(code, school, values):
    """Resolve a code only for the designated school and matching local intake."""
    if not isinstance(code, str) or len(code) > 512:
        raise ValueError("Code de transfert invalide.")
    try:
        payload = signing.loads(code.strip(), salt=SALT, max_age=MAX_AGE)
        if payload["destination"] != str(school.pk):
            raise ValueError
        source_id = UUID(payload["student"])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValueError("Code de transfert invalide ou expiré pour cet établissement.") from None
    source = Student.objects.filter(pk=source_id).exclude(school=school).first()
    if source is None or source.date_of_birth is None or (
        source.date_of_birth != values.get("date_of_birth")
        or source.first_name.casefold() != values["first_name"].casefold()
        or source.last_name.casefold() != values["last_name"].casefold()
    ):
        raise ValueError("Le code de transfert ne correspond pas à l’identité saisie.")
    return source.identity_id
