"""Private admissions workflow; public applicant intake is deliberately NOT exposed."""
import re
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import authorized

from .admission_models import AdmissionApplication, AdmissionEvent, AdmissionPolicy, AdmissionDocument
from .academic_models import AcademicYear, AcademicClass, AcademicLevel
from .student_models import Student, StudentGuardian, Enrollment, EnrollmentEvent
from .student_views import validate_enrollment_slot
from .services import has_permission, quota_reached
from .views import access, refuse, parse_body, log_event
from .admission_policy import (ROUTES, DOCUMENT_CODE, effective_policy, policy_view,
                               policy_key, validate_policy, required_for_route,
                               admission_blocker)

SOURCE_CODE = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
ALLOWED_TRANSITIONS = {
    "submitted": {"review", "accepted", "rejected"},
    "review": {"accepted", "rejected"},
}


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def uid(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def day(value, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Date ISO requise.")
    try:
        d = date.fromisoformat(value)
        if d.isoformat() != value:
            raise ValueError()
        return d
    except ValueError:
        raise ValueError("Date ISO invalide.") from None


def name(value, length, mandatory=False):
    if not isinstance(value, str) or len(value.strip()) > length or (mandatory and not value.strip()):
        raise ValueError("Champ texte invalide.")
    if any(ord(ch) < 32 for ch in value):
        raise ValueError("Caractère de contrôle interdit.")
    return value.strip()


def positive_revision(value):
    if type(value) is not int or value < 1:
        raise ValueError("Révision positive obligatoire.")
    return value


def gate(request, school_id, permission):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, permission):
        return None, refuse()
    return school, None


def render(row):
    return {
        "id": str(row.pk), "year": str(row.year_id),
        "classroom": str(row.classroom_id),
        "existing_student": str(row.existing_student_id) if row.existing_student_id else None,
        "enrollment": str(row.enrollment_id) if row.enrollment_id else None,
        "first_name": row.first_name, "last_name": row.last_name,
        "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else None,
        "guardian_name": row.guardian_name,
        "guardian_relationship": row.guardian_relationship,
        "guardian_phone": row.guardian_phone,
        "guardian_email": row.guardian_email,
        "source": row.source, "status": row.status,
        "route": row.route, "origin_school": row.origin_school,
        "route_reference": row.route_reference, "orientation_authority": row.orientation_authority,
        "external_result": row.external_result, "required_documents": row.required_documents,
        "decision_reason": row.decision_reason, "revision": row.revision,
        "submitted_at": row.submitted_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "converted_at": row.converted_at.isoformat() if row.converted_at else None,
    }


def model_error(exc):
    if hasattr(exc, "message_dict"):
        messages = [m for a in exc.message_dict.values() for m in a]
    else:
        messages = exc.messages
    return fail(" ".join(messages)[:600])


@require_http_methods(["GET", "POST"])
@authorized
def applications(request, school_id):
    school, error = gate(request, school_id,
                         "school.admissions.read" if request.method == "GET" else "school.admissions.manage")
    if error is not None:
        return error
    if request.method == "GET":
        rows = AdmissionApplication.objects.filter(school=school)
        if "year" in request.GET:
            year_id = uid(request.GET.get("year"))
            if year_id is None:
                return fail("Année scolaire invalide.")
            rows = rows.filter(year_id=year_id)
        if "classroom" in request.GET:
            classroom_id = uid(request.GET.get("classroom"))
            if classroom_id is None:
                return fail("Classe invalide.")
            rows = rows.filter(classroom_id=classroom_id)
        if "route" in request.GET:
            route = request.GET.get("route")
            if route not in ROUTES:
                return fail("Voie d'admission inconnue.")
            rows = rows.filter(route=route)
        if "status" in request.GET:
            code = request.GET.get("status")
            if code not in ("submitted", "review", "accepted", "rejected", "enrolled"):
                return fail("Statut inconnu.")
            rows = rows.filter(status=code)
        return JsonResponse({"applications": [render(row) for row in rows.order_by(
            "-submitted_at", "pk")[:500]]})
    data, error = parse_body(request)
    if error is not None:
        return error
    required = {"year", "classroom", "first_name", "last_name", "guardian_name", "source"}
    allowed = required | {"date_of_birth", "guardian_relationship",
                          "guardian_phone", "guardian_email", "existing_student",
                          "route", "origin_school", "route_reference", "orientation_authority"}
    if not isinstance(data, dict) or set(data) - allowed or not required <= set(data):
        return fail("Champs de préinscription incorrects.")
    try:
        year_id = uid(data["year"])
        class_id = uid(data["classroom"])
        existing_id = uid(data["existing_student"]) if data.get("existing_student") else None
        if not year_id or not class_id or ("existing_student" in data and data["existing_student"] and not existing_id):
            raise ValueError("Année, classe ou élève invalide.")
        first = name(data["first_name"], 120, mandatory=True)
        last = name(data["last_name"], 120, mandatory=True)
        guardian = name(data["guardian_name"], 180, mandatory=True)
        relation = name(data.get("guardian_relationship", ""), 80)
        phone = name(data.get("guardian_phone", ""), 45)
        email = name(data.get("guardian_email", ""), 254)
        birth = day(data.get("date_of_birth"), optional=True)
        source = data["source"]
        if not isinstance(source, str) or not SOURCE_CODE.fullmatch(source):
            raise ValueError("Source de candidature invalide.")
        route = data.get("route", "direct")
        if route not in ROUTES:
            raise ValueError("Voie d'admission invalide.")
        origin_school = name(data.get("origin_school", ""), 180)
        route_reference = name(data.get("route_reference", ""), 140)
        orientation_authority = name(data.get("orientation_authority", ""), 120)
        if route != "orientation" and orientation_authority:
            raise ValueError("L'autorité d'orientation concerne uniquement les affectations.")
        if not AcademicYear.objects.filter(school=school, pk=year_id, active=True).exists():
            raise ValueError("Année scolaire inactive ou étrangère.")
        if not AcademicClass.objects.filter(school=school, year_id=year_id, pk=class_id, active=True).exists():
            raise ValueError("Classe inactive ou étrangère.")
        if existing_id and not Student.objects.filter(school=school, pk=existing_id, active=True).exists():
            raise ValueError("Élève existant introuvable.")
        target_class = AcademicClass.objects.select_related("level").get(pk=class_id, school=school)
        policy = effective_policy(school, target_class.year, target_class.level)
        if route not in (policy.enabled_routes if policy else ROUTES):
            raise ValueError("Cette voie d'admission est désactivée pour le niveau.")
        required_docs = required_for_route(route, policy)
        with transaction.atomic():
            row = AdmissionApplication(
                school=school, year_id=year_id, classroom_id=class_id, existing_student_id=existing_id,
                first_name=first, last_name=last, date_of_birth=birth, guardian_name=guardian,
                guardian_relationship=relation, guardian_phone=phone, guardian_email=email,
                source=source, submitted_by=request.user, route=route,
                origin_school=origin_school, route_reference=route_reference,
                orientation_authority=orientation_authority,
                required_documents=required_docs,
            )
            row.full_clean()
            row.save()
            AdmissionEvent.objects.create(school=school, application=row, previous_status="",
                                          new_status="submitted", actor=request.user)
            log_event(school, request, "admission_submitted", row.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return model_error(exc)
    return JsonResponse(render(row), status=201)


@require_GET
@authorized
def application_detail(request, school_id, application_id):
    school, error = gate(request, school_id, "school.admissions.read")
    if error is not None:
        return error
    row = AdmissionApplication.objects.filter(school=school, pk=application_id).first()
    return JsonResponse(render(row)) if row else fail("Candidature introuvable.", 404)


@require_POST
@authorized
def decide(request, school_id, application_id):
    school, error = gate(request, school_id, "school.admissions.decide")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) != {"revision", "status", "reason"}:
        return fail("Révision, décision et motif requis.")
    try:
        revision = positive_revision(data["revision"])
        status = data["status"]
        reason = name(data["reason"], 1000, mandatory=(status in ("accepted", "rejected")))
        if status not in ("review", "accepted", "rejected"):
            raise ValueError("Décision invalide.")
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        row = AdmissionApplication.objects.select_for_update().filter(school=school, pk=application_id).first()
        if row is None:
            return fail("Candidature introuvable.", 404)
        if row.revision != revision:
            return JsonResponse({"error": "Conflit de version.", "revision": row.revision}, status=409)
        if status not in ALLOWED_TRANSITIONS.get(row.status, set()):
            return fail("Transition de candidature non autorisée.", 409)
        if status == "accepted":
            blocker = admission_blocker(row)
            if blocker:
                return fail(blocker, 409)
        previous = row.status
        row.status = status
        row.revision += 1
        if status in ("accepted", "rejected"):
            row.decision_reason = reason
            row.decided_at = timezone.now()
            row.decided_by = request.user
        row.full_clean()
        row.save()
        AdmissionEvent.objects.create(school=school, application=row, previous_status=previous,
                                      new_status=status, reason=reason, actor=request.user)
        log_event(school, request, "admission_decision", row.pk)
    return JsonResponse(render(row))



def verified_family_identity(application):
    """Reuse an identity only through the same immutable family profile and a verified link."""
    from .parent_admission_models import FamilyChild, ParentAdmissionRequest
    from .parent_models import GuardianAccountLink

    submission = ParentAdmissionRequest.objects.select_related("owner").filter(application=application).first()
    if submission is None:
        return None
    FamilyChild.objects.select_for_update().get(pk=submission.child_id, owner_id=submission.owner_id)
    prior = ParentAdmissionRequest.objects.filter(
        child_id=submission.child_id, owner_id=submission.owner_id,
        application__status="enrolled", application__enrollment__isnull=False,
    ).values("application__enrollment__student_id")
    identities = list(GuardianAccountLink.objects.filter(
        user_id=submission.owner_id, active=True, guardian__active=True,
        guardian__school_id=F("school_id"), guardian__student__school_id=F("school_id"),
        guardian__student_id__in=prior,
        guardian__student__first_name__iexact=application.first_name,
        guardian__student__last_name__iexact=application.last_name,
        guardian__student__date_of_birth=application.date_of_birth,
    ).order_by().values_list("guardian__student__identity_id", flat=True).distinct()[:2])
    if len(identities) == 1:
        return identities[0]
    if prior.exists():
        raise ValueError("Vérifiez le rattachement du responsable légal à l’ancien dossier avant la réinscription.")
    return None


@require_POST
@authorized
def convert(request, school_id, application_id):
    school, error = gate(request, school_id, "school.admissions.enroll")
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.students.manage"):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    if not {"revision", "enrolled_on"} <= set(data) or set(data) - {"revision", "enrolled_on", "student_code"}:
        return fail("Révision et date d’inscription obligatoires.")
    try:
        revision = positive_revision(data["revision"])
        enrolled_on = day(data["enrolled_on"])
    except ValueError as exc:
        return fail(str(exc))
    try:
        with transaction.atomic():
            row = AdmissionApplication.objects.select_for_update().filter(
                school=school, pk=application_id
            ).first()
            if row is None:
                return fail("Candidature introuvable.", 404)
            if row.status == "enrolled" and row.enrollment_id:
                return JsonResponse(render(row), status=200)
            if revision != row.revision:
                return JsonResponse({"error": "Conflit de version.", "revision": row.revision}, status=409)
            if row.status != "accepted":
                return fail("L'admission doit être validée avant inscription.", 409)
            from .models import School
            School.objects.select_for_update().get(pk=school.pk)
            identity = verified_family_identity(row)
            classroom = AcademicClass.objects.select_for_update().get(pk=row.classroom_id, school=school)
            student = row.existing_student
            if student is not None and identity is not None and student.identity_id != identity:
                return fail("Le dossier local sélectionné ne correspond pas au matricule YEM vérifié.", 409)
            if student is None and identity is not None:
                student = Student.objects.filter(school=school, identity_id=identity).first()
            new_student = student is None
            if new_student:
                if quota_reached(school, "students"):
                    return fail("Plafond d'élèves atteint pour cet établissement.", 409)
                student = Student(
                    school=school, identity_id=identity,
                    first_name=row.first_name, last_name=row.last_name,
                    date_of_birth=row.date_of_birth, admission_date=enrolled_on,
                )
                student.full_clean()
            elif not student.active:
                return fail("Dossier élève inactif.", 409)
            validate_enrollment_slot(classroom, student, row.year)
            if not row.year.start_date <= enrolled_on <= row.year.end_date:
                return fail("Inscription hors des dates de l'année scolaire.")
            if Enrollment.objects.filter(school=school, student=student, year=row.year).exists():
                return fail("Élève déjà inscrit pour cette année.", 409)
            if new_student:
                student.save()
            enrolled = Enrollment(
                school=school, student=student, year=row.year, classroom=classroom,
                enrolled_on=enrolled_on, status="inscrit",
            )
            enrolled.full_clean()
            enrolled.save()
            if new_student:
                guardian = StudentGuardian(
                    school=school, student=student, full_name=row.guardian_name,
                    relationship=row.guardian_relationship, phone=row.guardian_phone,
                    email=row.guardian_email, is_primary=True,
                )
                guardian.full_clean()
                guardian.save()
            EnrollmentEvent.objects.create(
                school=school, enrollment=enrolled, actor=request.user,
                previous_class_id=None, new_class_id=classroom.pk, new_status=enrolled.status,
            )
            row.enrollment = enrolled
            row.status = "enrolled"
            row.converted_at = timezone.now()
            row.revision += 1
            row.full_clean()
            row.save()
            AdmissionEvent.objects.create(school=school, application=row, previous_status="accepted",
                                          new_status="enrolled", actor=request.user)
            log_event(school, request, "admission_enrolled", row.pk)
    except ValidationError as exc:
        return model_error(exc)
    except ValueError as exc:
        return fail(str(exc))
    except IntegrityError:
        return fail("Inscription ou matricule déjà enregistré.", 409)
    return JsonResponse(render(row), status=201)


@require_GET
@authorized
def history(request, school_id, application_id):
    school, error = gate(request, school_id, "school.admissions.read")
    if error is not None:
        return error
    if not AdmissionApplication.objects.filter(school=school, pk=application_id).exists():
        return fail("Candidature introuvable.", 404)
    rows = AdmissionEvent.objects.filter(school=school, application_id=application_id).order_by("at", "pk")[:100]
    return JsonResponse({"history": [{
        "previous": row.previous_status, "status": row.new_status,
        "reason": row.reason, "actor": str(row.actor_id) if row.actor_id else None,
        "at": row.at.isoformat(),
    } for row in rows]})


@require_GET
@authorized
def capacity(request, school_id, classroom_id):
    school, error = gate(request, school_id, "school.admissions.read")
    if error is not None:
        return error
    classroom = AcademicClass.objects.filter(school=school, pk=classroom_id).first()
    if classroom is None:
        return fail("Classe introuvable.", 404)
    occupied = Enrollment.objects.filter(school=school, classroom=classroom, active=True).count()
    accepted = AdmissionApplication.objects.filter(school=school, classroom=classroom, status="accepted").count()
    return JsonResponse({
        "classroom": str(classroom.pk), "year": str(classroom.year_id),
        "capacity": classroom.capacity, "occupied": occupied, "accepted_pending": accepted,
        "remaining": max(0, classroom.capacity - occupied) if classroom.capacity is not None else None,
        "notice": "Admission acceptée ne réserve pas de place ; la capacité est recontrôlée à l'inscription.",
    })
