"""Internal, course-scoped curriculum delivery tracking (not student mastery)."""
from datetime import date
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .academic_models import AcademicYear
from .course_progress_models import CourseUnitProgress
from .curriculum_models import CourseUnit
from .models import School
from .services import has_permission
from .teaching_diary_models import TeachingDiaryEntry
from .teaching_diary_views import error, school_courses, uuid_value, writable
from .views import access, parse_body, refuse, log_event


STATUSES = ("not_started", "in_progress", "completed")


def iso(value):
    return value.isoformat() if value else None


def serialize(unit, row, today):
    status = row.status if row else "not_started"
    end = row.planned_end if row else None
    done = row.completed_on if row else None
    return {
        "id": str(unit.pk), "title": unit.title, "objectives": unit.objectives,
        "active": unit.active, "status": status, "revision": row.revision if row else 0,
        "planned_start": iso(row.planned_start) if row else None,
        "planned_end": iso(end), "completed_on": iso(done),
        "overdue": bool(end and end < today and status != "completed"),
        "completed_late": bool(end and done and done > end),
        "evidence": str(row.evidence_id) if row and row.evidence_id else None,
    }


def date_field(value, year):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Date invalide.")
    parsed = date.fromisoformat(value)
    if not year.start_date <= parsed <= year.end_date:
        raise ValueError("Date hors de l'année scolaire.")
    return parsed


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def progress(request, school_id, course_id):
    school, denied = access(request, school_id)
    if denied is not None:
        return denied
    if not has_permission(request.user, school, "school.curriculum.read"):
        return refuse()
    course = school_courses(request.user, school).filter(pk=course_id).first()
    if course is None:
        return error("Cours introuvable ou non autorisé.", 404)
    today = timezone.localdate()
    units = CourseUnit.objects.filter(school=school, course=course)
    if request.method == "GET":
        active = units.filter(active=True)
        summary = active.aggregate(
            total=Count("pk"),
            completed=Count("pk", filter=Q(progress__status="completed")),
            in_progress=Count("pk", filter=Q(progress__status="in_progress")),
            overdue=Count("pk", filter=Q(progress__planned_end__lt=today) & ~Q(progress__status="completed")),
            unplanned=Count("pk", filter=Q(progress__planned_end__isnull=True)),
            completed_late=Count("pk", filter=Q(progress__status="completed", progress__completed_on__gt=F("progress__planned_end"))),
        )
        summary["percent"] = round(100 * summary["completed"] / summary["total"]) if summary["total"] else None
        rows = units.select_related("progress").order_by("-active", "order", "pk")[:501]
        rows = list(rows)
        return JsonResponse({
            "units": [serialize(u, getattr(u, "progress", None), today) for u in rows[:500]],
            "summary": summary, "truncated": len(rows) > 500, "writable": writable(course),
            "year_start": iso(course.year.start_date), "year_end": iso(course.year.end_date),
        })

    body, denied = parse_body(request)
    if denied is not None:
        return denied
    if set(body) != {"unit", "revision", "planned_start", "planned_end", "status", "completed_on", "evidence"}:
        return error("Champs invalides.")
    if type(body["revision"]) is not int or body["revision"] < 0 or body["status"] not in STATUSES:
        return error("État ou révision invalide.")
    try:
        unit_id = uuid_value(body["unit"])
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            course = school_courses(request.user, school).filter(pk=course_id).first()
            if course is None:
                return error("Cours introuvable ou non autorisé.", 404)
            course.year = AcademicYear.objects.select_for_update().get(pk=course.year_id)
            if not writable(course):
                return error("Cours ou année non modifiable.", 409)
            unit = CourseUnit.objects.select_for_update().filter(school=school, course=course, pk=unit_id).first()
            if unit is None:
                return error("Chapitre introuvable.", 404)
            if not unit.active:
                return error("Chapitre archivé.", 409)
            start = date_field(body["planned_start"], course.year)
            end = date_field(body["planned_end"], course.year)
            done = date_field(body["completed_on"], course.year)
            status = body["status"]
            if start and end and start > end:
                return error("La fin prévue doit suivre le début.")
            if (status == "completed") != bool(done) or (done and done > today):
                return error("Date effective obligatoire pour un chapitre dispensé, non future.")
            evidence = None
            if body["evidence"] is not None:
                evidence = TeachingDiaryEntry.objects.filter(
                    course=course, pk=uuid_value(body["evidence"]),
                    day__gte=course.year.start_date, day__lte=min(today, course.year.end_date),
                ).first()
                if not evidence or status == "not_started" or (done and evidence.day > done):
                    return error("Séance justificative non autorisée ou incompatible.")
            row = CourseUnitProgress.objects.select_for_update().filter(unit=unit).first()
            values = dict(planned_start=start, planned_end=end, status=status, completed_on=done, evidence=evidence)
            actual = row.revision if row else 0
            # Safe replay of a successful update; a stale different payload conflicts.
            if row and all(getattr(row, key) == value for key, value in values.items()):
                return JsonResponse(serialize(unit, row, today))
            if actual != body["revision"]:
                return JsonResponse({"error":"Conflit de version. Actualisez.", "revision":actual}, status=409)
            before = serialize(unit, row, today)
            if row is None:
                row = CourseUnitProgress(unit=unit)
            else:
                row.revision += 1
            for key, value in values.items():
                setattr(row, key, value)
            row.updated_by = request.user
            row.save()
            after = serialize(unit, row, today)
            log_event(school, request, "course_unit_progress_updated", unit.pk, {
                "before": {k:before[k] for k in ("status","planned_start","planned_end","completed_on","evidence","revision")},
                "after": {k:after[k] for k in ("status","planned_start","planned_end","completed_on","evidence","revision")},
            })
            return JsonResponse(after)
    except ValueError as exc:
        return error(str(exc))
    except IntegrityError:
        return error("Écriture concurrente. Actualisez.", 409)
