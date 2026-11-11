"""School publication and withdrawal of messages for verified families."""
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from accounts.views import authorized

from institutions.academic_models import AcademicYear
from .models import ConductNotice
from institutions.attendance_views import authorized_for, choose_class, iso_date, text_field, uuid_value
from institutions.cycle_scope import has_cycle_scope
from institutions.student_models import Enrollment
from institutions.views import access, log_event, parse_body, refuse


def notice_output(row):
    return {
        "id": str(row.pk), "date": row.date.isoformat(), "kind": row.kind,
        "label": row.get_kind_display(), "message": row.message,
    }


def staff_notice_output(row):
    student = row.enrollment.student
    return {
        **notice_output(row), "student": f"{student.last_name} {student.first_name}",
        "withdrawn": row.withdrawn_at is not None,
    }


def conduct_scope(request, school_id, classroom_id):
    school, error = access(request, school_id)
    if error is not None:
        return None, None, error
    classroom = choose_class(school, str(classroom_id))
    if classroom is None:
        return None, None, JsonResponse({"error": "Classe introuvable."}, status=404)
    if (not authorized_for(request.user, school, classroom, "finalize")
            or not has_cycle_scope(request.user, school, classroom.level.cycle_id)):
        return None, None, refuse()
    return school, classroom, None


def class_enrollments(school, classroom):
    return Enrollment.objects.filter(
        school=school, classroom=classroom, year_id=classroom.year_id, student__school=school,
    )


def year_is_editable(year):
    return year.active and year.status != AcademicYear.STATUS_CLOSED


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def notices(request, school_id, classroom_id):
    school, classroom, error = conduct_scope(request, school_id, classroom_id)
    if error is not None:
        return error
    enrollments = class_enrollments(school, classroom)
    if request.method == "GET":
        roster = enrollments.filter(active=True, student__active=True).select_related("student").order_by(
            "student__last_name", "student__first_name", "pk",
        )
        rows = ConductNotice.objects.filter(enrollment__in=enrollments).select_related(
            "enrollment__student",
        ).order_by("-date", "-published_at", "pk")
        return JsonResponse({
            "roster": [{"id": str(row.pk), "name": f"{row.student.last_name} {row.student.first_name}",
                        "matricule": row.student.student_code} for row in roster],
            "notices": [staff_notice_output(row) for row in rows],
            "can_publish": year_is_editable(classroom.year) and classroom.active,
            "can_withdraw": year_is_editable(classroom.year),
        })
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"enrollment", "date", "kind", "message"}:
        return JsonResponse({"error": "Élève, date, type et message requis."}, status=422)
    enrollment_id = uuid_value(data["enrollment"])
    if enrollment_id is None or data["kind"] not in ConductNotice.Kind.values:
        return JsonResponse({"error": "Élève ou type invalide."}, status=422)
    try:
        date = iso_date(data["date"])
        message = text_field(data["message"], 500, required=True)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    with transaction.atomic():
        year = AcademicYear.objects.select_for_update(no_key=True).get(pk=classroom.year_id)
        if not year_is_editable(year) or not classroom.active:
            return JsonResponse({"error": "Cette classe ou année scolaire est archivée."}, status=409)
        enrollment = enrollments.select_related("student").select_for_update(of=("self",)).filter(
            pk=enrollment_id, active=True, student__active=True,
        ).first()
        if enrollment is None:
            return JsonResponse({"error": "Élève introuvable dans cette classe."}, status=404)
        if not max(year.start_date, enrollment.enrolled_on) <= date <= year.end_date:
            return JsonResponse({"error": "Date hors de la période d’inscription de l’élève."}, status=422)
        row, created = ConductNotice.objects.get_or_create(
            enrollment=enrollment, date=date, kind=data["kind"], message=message, withdrawn_at=None,
            defaults={"published_by": request.user},
        )
        if created:
            log_event(school, request, "conduct_notice_published", row.pk)
    return JsonResponse(staff_notice_output(row), status=201 if created else 200)


@never_cache
@require_POST
@authorized
def withdraw(request, school_id, classroom_id, notice_id):
    school, classroom, error = conduct_scope(request, school_id, classroom_id)
    if error is not None:
        return error
    with transaction.atomic():
        year = AcademicYear.objects.select_for_update(no_key=True).get(pk=classroom.year_id)
        if not year_is_editable(year):
            return JsonResponse({"error": "Cette année scolaire est archivée."}, status=409)
        row = ConductNotice.objects.select_related("enrollment__student").select_for_update(of=("self",)).filter(
            pk=notice_id, enrollment__in=class_enrollments(school, classroom),
        ).first()
        if row is None:
            return JsonResponse({"error": "Communication introuvable dans cette classe."}, status=404)
        if row.withdrawn_at is None:
            row.withdrawn_at = timezone.now()
            row.save(update_fields=["withdrawn_at"])
            log_event(school, request, "conduct_notice_withdrawn", row.pk)
    return JsonResponse(staff_notice_output(row))
