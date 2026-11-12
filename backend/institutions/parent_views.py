"""Module 15: read-only parent access to explicitly verified children.

No parent endpoint accepts a student/school ID as authorization in isolation:
it must resolve through an active, manually verified legal-guardian link and
an active parent-role membership in that same school.
"""
from types import SimpleNamespace
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from accounts.views import authorized
from conduct.models import ConductNotice
from conduct.views import notice_output

from .academic_models import AcademicYear
from .assessment_models import AssessmentGrade
from .attendance_models import AttendanceMark
from .council_models import ReportAmendment
from .finance_models import FeeCharge
from .finance_views import cleared_total
from .models import SchoolMember, School
from .parent_models import GuardianAccountLink
from .parent_admission_models import ParentAdmissionRequest, FamilyChildPhoto
from .report_models import SchoolReport
from .report_views import pdf_bytes
from .services import has_permission
from .student_models import StudentGuardian, Enrollment
from .timetable_models import TimetableEntry
from .views import access, refuse, parse_body, log_event

User = get_user_model()


def reject(message, status=422):
    return JsonResponse({"error": message}, status=status)


def uuid_input(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def guardian_links(user):
    """The account must be a current parent in the same active school."""
    return GuardianAccountLink.objects.select_related(
        "school", "guardian__student"
    ).filter(
        user=user, active=True,
        school__is_active=True,
        guardian__active=True,
        guardian__student__active=True,
        guardian__school_id=F("school_id"),
        guardian__student__school_id=F("school_id"),
        school__members__user=user,
        school__members__active=True,
        school__members__role__school_id=F("school_id"),
        school__members__role__code="parent",
    ).distinct()


def permitted_child(user, student_id):
    link = guardian_links(user).filter(guardian__student_id=student_id).first()
    if link is None:
        return None, reject("Enfant introuvable.", 404)
    return link.guardian.student, None


def child_scope(request, student_id):
    student, error = permitted_child(request.user, student_id)
    if error is not None:
        return None, None, error
    requested_year = request.GET.get("year")
    year_id = uuid_input(requested_year)
    if requested_year is not None and year_id is None:
        return None, None, reject("Année scolaire invalide.")
    return student, year_id, None


def link_output(row):
    return {
        "id": str(row.pk), "school": str(row.school_id),
        "guardian": str(row.guardian_id), "student": str(row.guardian.student_id),
        "guardian_name": row.guardian.full_name,
        "student_name": f"{row.guardian.student.last_name} {row.guardian.student.first_name}",
        "username": row.user.get_username(), "active": row.active,
        "revision": row.revision, "verified_at": row.verified_at.isoformat(),
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }


def admin_gate(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, "school.parents.manage"):
        return None, refuse()
    return school, None


def model_error(exc):
    if hasattr(exc, "message_dict"):
        parts = [value for values in exc.message_dict.values() for value in values]
    else:
        parts = exc.messages
    return reject(" ".join(parts)[:500])


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def links(request, school_id):
    school, error = admin_gate(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        result = GuardianAccountLink.objects.select_related("guardian__student", "user").filter(
            school=school
        ).order_by("-verified_at", "pk")[:250]
        return JsonResponse({"links": [link_output(row) for row in result]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"guardian", "username"}:
        return reject("Responsable légal et compte utilisateur requis.")
    guardian_id = uuid_input(data["guardian"])
    username = data["username"]
    if guardian_id is None or not isinstance(username, str) or not 1 <= len(username.strip()) <= 150:
        return reject("Responsable légal ou compte invalide.")
    username = username.strip()
    try:
        with transaction.atomic():
            guardian = StudentGuardian.objects.select_related("student").filter(
                school=school, pk=guardian_id, active=True, student__active=True,
            ).first()
            if guardian is None:
                return reject("Responsable légal introuvable.", 404)
            # User lookup alone is not proof. A human administrator has to assign
            # the parent role to this existing active account before verification.
            member = SchoolMember.objects.select_related("user", "role").filter(
                school=school, user__username=username, user__is_active=True,
                active=True, role__school=school, role__code="parent",
            ).first()
            if member is None:
                return reject("Attribuez d'abord le rôle parent au compte actif dans cette école.", 422)
            row = GuardianAccountLink.objects.select_for_update().filter(
                school=school, guardian=guardian, user=member.user
            ).first()
            if row is not None and row.active:
                return reject("Compte déjà associé à ce responsable légal.", 409)
            if row is None:
                row = GuardianAccountLink(
                    school=school, guardian=guardian, user=member.user, verified_by=request.user
                )
                row.full_clean()
                row.save()
            else:
                row.active = True
                row.revision += 1
                row.verified_at = timezone.now()
                row.verified_by = request.user
                row.revoked_at = None
                row.revoked_by = None
                row.full_clean()
                row.save()
            log_event(school, request, "parent_link_verified", row.pk)
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return reject("Association déjà enregistrée.", 409)
    return JsonResponse(link_output(row), status=201)


@never_cache
@require_http_methods(["PATCH"])
@authorized
def link_detail(request, school_id, link_id):
    school, error = admin_gate(request, school_id)
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"revision", "active"} or type(data["revision"]) is not int or data["revision"] < 1 or data["active"] is not False:
        return reject("Seule la révocation avec révision valide est autorisée.")
    with transaction.atomic():
        row = GuardianAccountLink.objects.select_for_update().select_related(
            "guardian__student", "user"
        ).filter(school=school, pk=link_id).first()
        if row is None:
            return reject("Association introuvable.", 404)
        if row.revision != data["revision"]:
            return JsonResponse({"error": "Conflit de version.", "revision": row.revision}, status=409)
        if not row.active:
            return reject("Association déjà révoquée.", 409)
        row.active = False
        row.revision += 1
        row.revoked_by = request.user
        row.revoked_at = timezone.now()
        row.save(update_fields=["active", "revision", "revoked_by", "revoked_at"])
        log_event(school, request, "parent_link_revoked", row.pk)
    return JsonResponse(link_output(row))


@never_cache
@require_GET
@authorized
def children(request):
    # Multiple verified guardians for one student must not duplicate the card.
    rows = guardian_links(request.user).order_by("school__name", "guardian__student__last_name", "guardian__student_id")
    linked = list(rows[:500])
    student_ids = [row.guardian.student_id for row in linked]
    family_requests = list(ParentAdmissionRequest.objects.select_related(
        "application", "application__enrollment"
    ).filter(owner=request.user).filter(
        Q(application__enrollment__student_id__in=student_ids)
        | Q(application__existing_student_id__in=student_ids)
    ))
    photo_children = set(FamilyChildPhoto.objects.filter(
        child_id__in=[entry.child_id for entry in family_requests]
    ).values_list("child_id", flat=True))
    photo_lookup = {}
    for entry in family_requests:
        if entry.child_id not in photo_children:
            continue
        student_id = (
            entry.application.enrollment.student_id if entry.application.enrollment_id
            else entry.application.existing_student_id
        )
        if student_id:
            photo_lookup[(entry.application.school_id, student_id)] = (
                f"/api/v1/parents/family-children/{entry.child_id}/photo"
            )
    result = {}
    for row in linked:
        student = row.guardian.student
        result[str(student.pk)] = {
            "student": str(student.pk), "school": str(row.school_id),
            "school_name": row.school.name,
            "first_name": student.first_name, "last_name": student.last_name,
            "student_code": student.student_code, "matricule_yem": student.matricule_yem,
            "photo_url": photo_lookup.get((row.school_id, student.pk)),
        }
    has_parent_role = SchoolMember.objects.filter(
        user=request.user, active=True, school__is_active=True,
        role__school_id=F("school_id"), role__code="parent"
    ).exists()
    return JsonResponse({"children": list(result.values()), "parent_role": has_parent_role,
                         "parent_username": request.user.get_username()})


@never_cache
@require_GET
@authorized
def child_enrollments(request, student_id):
    student, error = permitted_child(request.user, student_id)
    if error is not None:
        return error
    rows = list(Enrollment.objects.select_related("year", "classroom").filter(
        school_id=student.school_id, student=student,
        year__school_id=student.school_id, classroom__school_id=student.school_id,
    ).order_by("-year__start_date", "pk")[:100])
    counts = dict(Enrollment.objects.filter(
        school_id=student.school_id, classroom_id__in=[row.classroom_id for row in rows],
        year_id=F("classroom__year_id"), active=True,
    ).values("classroom_id").annotate(total=Count("pk")).values_list("classroom_id", "total"))
    today = timezone.localdate()
    return JsonResponse({"student": str(student.pk), "enrollments": [{
        "id": str(row.pk), "year": row.year.name, "year_id": str(row.year_id),
        "classroom": row.classroom.name, "classroom_id": str(row.classroom_id),
        "class_size": counts.get(row.classroom_id, 0), "enrolled_on": row.enrolled_on.isoformat(),
        "year_status": row.year.status,
        "year_in_progress": row.year.active and row.year.start_date <= today <= row.year.end_date,
        "status": row.status, "active": row.active,
    } for row in rows]})


@never_cache
@require_GET
@authorized
def child_grades(request, student_id):
    student, year_id, error = child_scope(request, student_id)
    if error is not None:
        return error
    grades = AssessmentGrade.objects.select_related("assessment__course__subject", "assessment__period").filter(
        school_id=student.school_id, enrollment__school_id=student.school_id, enrollment__student=student,
        assessment__school_id=student.school_id, assessment__course__school_id=student.school_id,
        assessment__course__year_id=F("enrollment__year_id"), assessment__published=True,
    )
    if year_id:
        grades = grades.filter(enrollment__year_id=year_id)
    items = []
    for grade in grades.order_by("-assessment__assessment_date", "assessment__course__subject__name", "pk"):
        assessment = grade.assessment
        scale = assessment.policy_snapshot.get("scale", {})
        items.append({
            "id": str(grade.pk), "subject": assessment.course.subject.name,
            "assessment": assessment.name, "date": assessment.assessment_date.isoformat(),
            "period": assessment.period.name if assessment.period else None,
            "score": grade.score, "scale_kind": scale.get("kind"), "scale_max": scale.get("max"),
            "label": grade.label, "weight": str(assessment.weight),
        })
    return JsonResponse({"student": str(student.pk), "grades": items})


def report_for_child(student, report_id):
    return SchoolReport.objects.filter(
        school_id=student.school_id, enrollment__student=student,
        status="published", pk=report_id,
    ).first()


def latest_document(row):
    amend = ReportAmendment.objects.filter(
        school_id=row.school_id, report=row
    ).order_by("-sequence").first()
    return amend.snapshot if amend else row.snapshot, amend


@never_cache
@require_GET
@authorized
def child_reports(request, student_id):
    student, year_id, error = child_scope(request, student_id)
    if error is not None:
        return error
    reports = SchoolReport.objects.select_related("period", "year").filter(
        school_id=student.school_id, enrollment__student=student, status="published"
    )
    if year_id:
        reports = reports.filter(year_id=year_id)
    items = []
    for row in reports.order_by("-published_at", "pk")[:100]:
        snapshot, amendment = latest_document(row)
        overall = snapshot.get("overall", {})
        items.append({
            "id": str(row.pk), "enrollment": str(row.enrollment_id),
            "period": row.period.name if row.period else "Année entière",
            "year": row.year.name, "published_at": row.published_at.isoformat() if row.published_at else None,
            "score": overall.get("score"), "label": overall.get("label"),
            "amendment_sequence": amendment.sequence if amendment else None,
        })
    return JsonResponse({"student": str(student.pk), "reports": items})


@never_cache
@require_GET
@authorized
def child_report_detail(request, student_id, report_id):
    student, error = permitted_child(request.user, student_id)
    if error is not None:
        return error
    row = report_for_child(student, report_id)
    if row is None:
        return reject("Bulletin introuvable.", 404)
    snapshot, amendment = latest_document(row)
    return JsonResponse({
        "id": str(row.pk), "snapshot": snapshot,
        "amendment_sequence": amendment.sequence if amendment else None,
        "published_at": row.published_at.isoformat() if row.published_at else None,
    })


@never_cache
@require_GET
@authorized
def child_report_pdf(request, student_id, report_id):
    student, error = permitted_child(request.user, student_id)
    if error is not None:
        return error
    row = report_for_child(student, report_id)
    if row is None:
        return reject("Bulletin introuvable.", 404)
    snapshot, amendment = latest_document(row)
    source = SimpleNamespace(snapshot=snapshot, status="published", pk=row.pk)
    response = HttpResponse(pdf_bytes(source), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="yem-bulletin-{str(row.pk)[:8]}'
        + (f'-rectificatif-{amendment.sequence}' if amendment else "") + '.pdf"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@never_cache
@require_GET
@authorized
def child_attendance(request, student_id):
    student, year_id, error = child_scope(request, student_id)
    if error is not None:
        return error
    # Only completed registers can be viewed by families. Do not expose internal
    # staff notes or evidence submitted by other people.
    rows = AttendanceMark.objects.filter(
        school_id=student.school_id, enrollment__school_id=student.school_id, enrollment__student=student,
        session__school_id=student.school_id, session__closed_at__isnull=False,
        session__classroom__year_id=F("enrollment__year_id"),
    )
    notices = ConductNotice.objects.filter(enrollment__school_id=student.school_id, enrollment__student=student,
                                           withdrawn_at__isnull=True)
    if year_id:
        rows = rows.filter(enrollment__year_id=year_id)
        notices = notices.filter(enrollment__year_id=year_id)
    totals = rows.aggregate(
        absent=Count("pk", filter=Q(status_group="absent")),
        late=Count("pk", filter=Q(status_group="late")),
        present=Count("pk", filter=Q(status_group="present")),
    )
    rows = rows.select_related("session").order_by("-session__attendance_date", "session__slot", "pk")
    if not year_id:
        rows = rows[:200]
    items = [{
        "id": str(row.pk), "date": row.session.attendance_date.isoformat(), "slot": row.session.label,
        "status": row.status_label, "group": row.status_group,
        "justified": row.justified,
    } for row in rows]
    return JsonResponse({"student": str(student.pk), "attendance": items, "totals": totals,
                         "conduct": [notice_output(row) for row in notices.order_by("-date", "-published_at")]})


@never_cache
@require_GET
@authorized
def child_finance(request, student_id):
    student, year_id, error = child_scope(request, student_id)
    if error is not None:
        return error
    charges = FeeCharge.objects.filter(
        school_id=student.school_id, enrollment__student=student,
    )
    enrollments = Enrollment.objects.filter(school_id=student.school_id, student=student)
    if year_id:
        charges = charges.filter(enrollment__year_id=year_id)
        enrollments = enrollments.filter(year_id=year_id)
    else:
        enrollments = enrollments.filter(active=True)
    from decimal import Decimal
    totals = {}
    items = []
    for row in charges.order_by("created_at", "pk")[:200]:
        paid = cleared_total(row)
        currency = row.currency
        amounts = totals.setdefault(currency, {
            "billed": Decimal("0.00"), "paid": Decimal("0.00"), "balance": Decimal("0.00"),
        })
        amounts["billed"] += row.amount
        amounts["paid"] += paid
        amounts["balance"] += row.amount - paid
        items.append({
            "id": str(row.pk), "label": row.label, "amount": str(row.amount),
            "currency": currency, "paid": str(paid),
            "balance": str(row.amount - paid),
            "due_date": row.due_date.isoformat() if row.due_date else None,
        })
    from .admission_finance import scholarship_for_enrollment
    current_enrollment = enrollments.order_by("-year__start_date").first()
    award = scholarship_for_enrollment(current_enrollment) if current_enrollment else None
    return JsonResponse({
        "scholarship": ({"sponsor": "État", "coverage": award.coverage,
                         "reference": award.official_reference} if award else None),
        "student": str(student.pk), "charges": items,
        "totals": {currency: {key: str(amount) for key, amount in totals.items()}
                   for currency, totals in totals.items()},
        "notice": "Journal des encaissements saisis par l'école, sans confirmation bancaire automatique.",
    })


@never_cache
@require_GET
@authorized
def child_timetable(request, student_id):
    student, year_id, error = child_scope(request, student_id)
    if error is not None:
        return error
    enrollments = Enrollment.objects.filter(school_id=student.school_id, student=student)
    if year_id:
        enrollments = enrollments.filter(year_id=year_id)
    else:
        enrollments = enrollments.filter(active=True)
    class_ids = enrollments.values_list("classroom_id", flat=True)
    entries = TimetableEntry.objects.select_related(
        "slot", "room", "course__subject", "instructor__staff_assignment__staff"
    ).filter(
        school_id=student.school_id, classroom_id__in=class_ids, active=True,
    ).order_by("weekday", "slot__start_time", "pk")[:250]
    return JsonResponse({"student": str(student.pk), "entries": [{
        "id": str(entry.pk), "classroom": str(entry.classroom_id),
        "subject": entry.course.subject.name, "teacher": (
            entry.instructor.staff_assignment.staff.first_name + " " +
            entry.instructor.staff_assignment.staff.last_name
        ),
        "weekday": entry.weekday,
        "from": entry.effective_from.isoformat(), "to": entry.effective_to.isoformat(),
        "start": entry.slot.start_time.strftime("%H:%M"),
        "end": entry.slot.end_time.strftime("%H:%M"),
        "room": entry.room.name if entry.room else None,
    } for entry in entries]})
