"""Secondary mastery and remediation: explicit teacher observations, never inferred grades."""
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .models import School
from .academic_models import AcademicYear
from .curriculum_models import CourseUnit
from .course_progress_views import date_field
from .remediation_models import SecondaryMastery
from .school_functions import SECONDARY
from .student_models import Enrollment
from .services import has_permission
from .teaching_diary_views import school_courses, writable, error, uuid_value
from .views import access, refuse, parse_body, log_event


def roster(school, course):
    return Enrollment.objects.filter(
        school=school, year=course.year, classroom=course.classroom,
        student__school=school, student__active=True, active=True, status="inscrit",
    )


def marks(school, course):
    return SecondaryMastery.objects.filter(
        unit__school=school, unit__course=course,
        enrollment__in=roster(school, course),
    )


def output(row, today):
    return {"unit":str(row.unit_id), "stage":row.stage, "action":row.action,
        "action_status":row.action_status, "due_on":row.due_on.isoformat() if row.due_on else None,
        "overdue":bool(row.due_on and row.due_on<today and row.action_status in ("planned","ongoing")),
        "unit_title":row.unit_title, "objectives_snapshot":row.objectives_snapshot,
        "revision":row.revision}


@never_cache
@require_http_methods(["GET","PATCH"])
@authorized
def remediation(request, school_id, course_id):
    school, denied = access(request, school_id)
    if denied is not None:
        return denied
    if not has_permission(request.user, school, "school.curriculum.read"):
        return refuse()
    courses = school_courses(request.user, school).filter(classroom__level__cycle__code__in=SECONDARY)
    course = courses.filter(pk=course_id).first()
    if course is None:
        return error("Cours secondaire introuvable ou non autorisé.",404)
    today = timezone.localdate()
    if request.method == "GET":
        students = roster(school,course)
        units = CourseUnit.objects.filter(school=school,course=course,active=True)
        if "enrollment" not in request.GET:
            # No bulk export of individual assessments. Return only the class roster.
            return JsonResponse({"students":[{"id":str(e.pk),"name":e.student.last_name+" "+e.student.first_name}
                for e in students.select_related("student").order_by("student__last_name","student__first_name","pk")[:500]],
                "truncated": students.count()>500, "writable":writable(course)})
        try:
            enrollment_id = uuid_value(request.GET["enrollment"])
        except ValueError:
            return error("Inscription invalide.")
        enrollment = students.filter(pk=enrollment_id).first()
        if enrollment is None:
            return error("Inscription introuvable.",404)
        records = {r.unit_id:r for r in marks(school,course).filter(enrollment=enrollment)}
        units = CourseUnit.objects.filter(school=school,course=course).order_by("-active","order","pk")
        units = list(units[:501])
        results = []
        for u in units[:500]:
            row = records.get(u.pk)
            if row is None and not u.active:
                continue
            results.append({"id":str(u.pk),"title":u.title,"objectives":u.objectives,"active":u.active,
                "mark":output(row,today) if row else None})
        return JsonResponse({"units":results,"truncated":len(units)>500,"writable":writable(course),
            "year_start":course.year.start_date.isoformat(),"year_end":course.year.end_date.isoformat()})
    body, denied = parse_body(request)
    if denied is not None:
        return denied
    if set(body)!={"unit","enrollment","revision","stage","action","action_status","due_on"}:
        return error("Champs invalides.")
    if type(body["revision"]) is not int or body["revision"]<0 or body["stage"] not in ("not_yet","developing","achieved") or body["action_status"] not in ("","planned","ongoing","completed"):
        return error("État ou révision invalide.")
    if not isinstance(body["action"],str) or len(body["action"].strip())>500:
        return error("Action invalide.")
    action=body["action"].strip()
    if bool(action)!=bool(body["action_status"]) or (not action and body["due_on"] is not None):
        return error("Précisez une action et son état, ou laissez les deux vides.")
    try:
        unit_id=uuid_value(body["unit"])
        enrollment_id=uuid_value(body["enrollment"])
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            course=courses.filter(pk=course_id).first()
            if course is None:
                return error("Cours non autorisé.",404)
            course.year=AcademicYear.objects.select_for_update().get(pk=course.year_id)
            if not writable(course):
                return error("Année ou cours non modifiable.",409)
            unit=CourseUnit.objects.select_for_update().filter(school=school,course=course,pk=unit_id,active=True).first()
            enrollment=roster(school,course).select_for_update().filter(pk=enrollment_id).first()
            if unit is None or enrollment is None:
                return error("Chapitre ou inscription introuvable.",404)
            due=date_field(body["due_on"],course.year)
            row=marks(school,course).select_for_update(of=("self",)).filter(unit=unit,enrollment=enrollment).first()
            values={"stage":body["stage"],"action":action,"action_status":body["action_status"],"due_on":due}
            if row and all(getattr(row,k)==v for k,v in values.items()):
                return JsonResponse(output(row,today))
            if (row.revision if row else 0)!=body["revision"]:
                return error("Conflit de version. Actualisez.",409)
            previous={"stage":row.stage,"action_status":row.action_status,"revision":row.revision} if row else None
            if row is None:
                row=SecondaryMastery(unit=unit,enrollment=enrollment,unit_title=unit.title,objectives_snapshot=unit.objectives)
            else:
                row.revision+=1
            for k,v in values.items():
                setattr(row,k,v)
            row.updated_by=request.user
            row.save()
            log_event(school,request,"secondary_mastery_updated",row.pk,{"before":previous,
                "after":{"stage":row.stage,"action_status":row.action_status,"revision":row.revision}})
            return JsonResponse(output(row,today))
    except ValueError as exc:
        return error(str(exc))
    except IntegrityError:
        return error("Écriture concurrente. Actualisez.",409)
