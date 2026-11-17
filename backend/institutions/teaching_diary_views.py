"""Teacher-assigned, school/cycle-scoped diary and published family view."""
from datetime import date
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F, Q, Prefetch
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_GET
from accounts.views import authorized
from .academic_models import AcademicYear
from .curriculum_models import CourseOffering
from .cycle_scope import scoped_cycle_ids
from .models import School
from .parent_views import child_scope
from .services import has_permission
from .student_models import Enrollment
from .teaching_diary_models import TeachingDiaryEntry
from .diary_resource_models import DiaryResource
from .views import access, parse_body, refuse, log_event


def error(message, status=422):
    return JsonResponse({"error": message}, status=status)


def uuid_value(value):
    if not isinstance(value, str):
        raise ValueError("Identifiant invalide.")
    return UUID(value)


def school_courses(user, school):
    rows = CourseOffering.objects.filter(
        school=school, year__school=school, classroom__school=school,
        classroom__year_id=F("year_id"), classroom__level__school=school,
        classroom__level__cycle__school=school, subject__school=school,
    ).select_related("subject", "classroom__level__cycle", "year")
    scope = scoped_cycle_ids(user, school)
    if scope is not None:
        rows = rows.filter(classroom__level__cycle_id__in=scope)
    if not has_permission(user, school, "school.curriculum.manage"):
        rows = rows.filter(
            instructors__school=school, instructors__active=True,
            instructors__staff_assignment__school=school,
            instructors__staff_assignment__year_id=F("year_id"),
            instructors__staff_assignment__classroom_id=F("classroom_id"),
            instructors__staff_assignment__active=True,
            instructors__staff_assignment__staff__school=school,
            instructors__staff_assignment__staff__active=True,
            instructors__staff_assignment__staff__account=user,
        ).distinct()
    return rows


def writable(course):
    return (course.active and course.year.active and course.year.status != "closed"
            and course.classroom.active and course.classroom.level.active
            and course.classroom.level.cycle.active and course.subject.active)


def resource_prefetch():
    return Prefetch("resources", queryset=DiaryResource.objects.filter(active=True).defer("data").order_by("created_at","pk"), to_attr="visible_resources")


def output(row, family=False):
    result = {"id": str(row.pk), "day": row.day.isoformat(), "title": row.title,
              "lesson": row.lesson, "homework": row.homework,
              "due_on": row.due_on.isoformat() if row.due_on else None,
              "subject": row.course.subject.name, "classroom": row.course.classroom.name}
    resources = getattr(row, "visible_resources", None)
    if resources is None:
        resources = row.resources.filter(active=True).defer("data").order_by("created_at","pk")
    result["resources"] = [{"id":str(r.pk),"filename":r.filename,"size":r.size} for r in resources]
    if not family:
        result.update(published=row.published, revision=row.revision)
    return result


def fields(body, course):
    required = {"day", "title", "lesson", "homework", "due_on", "published"}
    if set(body) != required or type(body["published"]) is not bool:
        raise ValueError("Champs invalides.")
    values = {}
    for key, limit in (("title", 180), ("lesson", 4000), ("homework", 4000)):
        val = body[key]
        if not isinstance(val, str) or len(val.strip()) > limit or (key != "homework" and not val.strip()):
            raise ValueError("Titre ou contenu invalide.")
        values[key] = val.strip()
    if not isinstance(body["day"], str):
        raise ValueError("Date invalide.")
    values["day"] = date.fromisoformat(body["day"])
    if not course.year.start_date <= values["day"] <= course.year.end_date:
        raise ValueError("Séance hors de l'année scolaire.")
    due = body["due_on"]
    if due is not None:
        if not isinstance(due, str):
            raise ValueError("Échéance invalide.")
        due = date.fromisoformat(due)
        if not values["homework"] or not values["day"] <= due <= course.year.end_date:
            raise ValueError("Échéance incompatible avec le devoir ou l'année.")
    values.update(due_on=due, published=body["published"])
    return values


@never_cache
@require_GET
@authorized
def catalog(request, school_id):
    school, denied = access(request, school_id)
    if denied is not None:
        return denied
    if not has_permission(request.user, school, "school.curriculum.read"):
        return refuse()
    rows = school_courses(request.user, school)
    if request.GET.get("year"):
        try:
            rows = rows.filter(year_id=uuid_value(request.GET["year"]))
        except ValueError:
            return error("Année invalide.")
    return JsonResponse({"courses": [
        {"id": str(c.pk), "subject": c.subject.name, "classroom": c.classroom.name,
         "year": str(c.year_id), "year_name": c.year.name, "writable": writable(c)}
        for c in rows.order_by("-year__start_date", "classroom__name", "subject__name", "pk")[:1000]]})


@never_cache
@require_http_methods(["GET", "POST", "PATCH"])
@authorized
def diary(request, school_id, course_id):
    school, denied = access(request, school_id)
    if denied is not None:
        return denied
    if not has_permission(request.user, school, "school.curriculum.read"):
        return refuse()
    courses = school_courses(request.user, school)
    course = courses.filter(pk=course_id).first()
    if course is None:
        return error("Cours introuvable ou non autorisé.", 404)
    if request.method == "GET":
        return JsonResponse({"entries": [output(row) for row in TeachingDiaryEntry.objects.filter(course=course)
            .select_related("course__subject", "course__classroom").prefetch_related(resource_prefetch()).order_by("-day", "-created_at", "pk")[:200]],
            "writable": writable(course)})
    body, denied = parse_body(request)
    if denied is not None:
        return denied
    try:
        key = uuid_value(body.pop("id", None))
        revision = body.pop("revision", None)
        if request.method == "PATCH" and (type(revision) is not int or revision < 1):
            return error("Révision obligatoire.")
        if request.method == "POST" and revision is not None:
            return error("Révision inattendue.")
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            course = school_courses(request.user, school).filter(pk=course_id).first()
            if course is None:
                return error("Cours introuvable ou non autorisé.", 404)
            course.year = AcademicYear.objects.select_for_update().get(pk=course.year_id)
            if not writable(course):
                return error("Cours ou année non modifiable.", 409)
            values = fields(body, course)
            row = TeachingDiaryEntry.objects.select_for_update().filter(pk=key, course=course).first()
            if request.method == "POST":
                if row:
                    if row.author_id == request.user.pk and all(getattr(row,k)==v for k,v in values.items()):
                        return JsonResponse(output(row))
                    return error("Identifiant déjà utilisé.", 409)
                row = TeachingDiaryEntry.objects.create(pk=key, course=course, author=request.user, **values)
                log_event(school, request, "diary_created", row.pk, {"published": row.published})
                return JsonResponse(output(row), status=201)
            if row is None:
                return error("Séance introuvable.", 404)
            if row.revision != revision:
                return error("La séance a été modifiée. Actualisez.", 409)
            for k, v in values.items():
                setattr(row, k, v)
            row.revision += 1
            row.save()
            log_event(school, request, "diary_updated", row.pk, {"published": row.published})
            return JsonResponse(output(row))
    except ValueError as exc:
        return error(str(exc))
    except IntegrityError:
        return error("Écriture concurrente. Actualisez.", 409)


def family_entries(student, year_id):
    enrollments = Enrollment.objects.filter(school=student.school, student=student,
        year__school=student.school, classroom__school=student.school,
        classroom__year_id=F("year_id"), active=True)
    if year_id:
        enrollments = enrollments.filter(year_id=year_id)
    else:
        enrollments = enrollments.filter(year__active=True)
    # Unique registration per school and year; constrain both class and dates.
    conditions = Q(pk__in=[])
    for e in enrollments:
        conditions |= Q(course__classroom_id=e.classroom_id, course__year_id=e.year_id, day__gte=e.enrolled_on)
    return TeachingDiaryEntry.objects.filter(conditions, course__school=student.school,
        course__subject__school=student.school, published=True)


@never_cache
@require_GET
@authorized
def child_diary(request, student_id):
    student, year_id, denied = child_scope(request, student_id)
    if denied is not None:
        return denied
    rows = family_entries(student, year_id).select_related("course__subject","course__classroom").prefetch_related(resource_prefetch())
    return JsonResponse({"entries": [output(row, family=True) for row in rows.order_by("-day","-created_at","pk")[:200]]})
