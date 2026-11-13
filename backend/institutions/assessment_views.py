"""Draft assessments with immutable grading policy snapshots and school-specific gradebooks."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods
from accounts.views import authorized
from pedagogy.domain import validate_policy, evaluate, ValidationError as PolicyError

from .views import access, refuse, parse_body, log_event
from .services import has_permission, resolve_settings
from .curriculum_models import CourseOffering, CourseInstructor
from .academic_models import AcademicPeriod
from .student_models import Enrollment
from .assessment_models import Assessment, AssessmentGrade


def can_use(user,school,course,write=False):
    perm="school.assessments.manage" if write else "school.assessments.read"
    if has_permission(user,school,perm):return True
    return CourseInstructor.objects.filter(
        school=school,course=course,active=True,
        staff_assignment__active=True,
        staff_assignment__staff__active=True,
        staff_assignment__staff__account=user,
    ).exists()


def course_access(request,school_id,course_id,write=False):
    school,error=access(request,school_id)
    if error is not None:return None,None,error
    course=CourseOffering.objects.select_related("classroom__level__cycle","year").filter(school=school,pk=course_id).first()
    if course is None or not can_use(request.user,school,course,write):
        return None,None,JsonResponse({"error":"Cours introuvable ou non autorisé."},status=404)
    return school,course,None


def assessment_access(request,school_id,assessment_id,write=False):
    school,error=access(request,school_id)
    if error is not None:return None,None,error
    assessment=Assessment.objects.select_related("course__year","course__classroom").filter(school=school,pk=assessment_id).first()
    if assessment is None or not can_use(request.user,school,assessment.course,write):
        return None,None,JsonResponse({"error":"Évaluation introuvable ou non autorisée."},status=404)
    return school,assessment,None


def decimal_input(value):
    if type(value) not in (int,float,str):raise ValueError("Pondération invalide.")
    try: result=Decimal(str(value))
    except (ValueError,InvalidOperation):raise ValueError("Pondération invalide.") from None
    if not result.is_finite() or not Decimal("0")<result<=Decimal("1000"):
        raise ValueError("Pondération hors limites.")
    return result


def date_input(value):
    if not isinstance(value,str):raise ValueError("Date ISO requise.")
    try:
        result=date.fromisoformat(value)
        if result.isoformat()!=value:raise ValueError()
        return result
    except ValueError:raise ValueError("Date ISO invalide.") from None


def fields(data, *, updating=False):
    allowed={"name","kind","assessment_date","weight","period","active"}
    if updating:allowed-={"period"}
    if set(data)-allowed-({"revision"} if updating else set()):
        raise ValueError("Champs inconnus ou non modifiables.")
    if not updating and not {"name","assessment_date"} <= set(data):
        raise ValueError("Nom et date obligatoires.")
    if updating and (type(data.get("revision")) is not int or data["revision"]<1 or len(data)==1):
        raise ValueError("Révision invalide.")
    clean={}
    for k,v in data.items():
        if k=="revision":continue
        if k=="name":
            if not isinstance(v,str) or not 1<=len(v.strip())<=180:raise ValueError("Nom invalide.")
            v=v.strip()
        elif k=="assessment_date":v=date_input(v)
        elif k=="kind":
            if not isinstance(v,str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,49}",v):raise ValueError("Type invalide.")
        elif k=="weight":v=decimal_input(v)
        elif k=="period":
            if v is not None:
                try:v=UUID(v)
                except (TypeError,ValueError,AttributeError):raise ValueError("Période invalide.") from None
            k="period_id"
        elif k=="active":
            if type(v) is not bool:raise ValueError("Statut invalide.")
        clean[k]=v
    return clean


def serialize(a):
    return {
        "id":str(a.pk),"course":str(a.course_id),
        "period":str(a.period_id) if a.period_id else None,
        "name":a.name,"kind":a.kind,
        "assessment_date":a.assessment_date.isoformat(),
        "weight":f"{a.weight:.3f}","active":a.active,"published":a.published,
        "revision":a.revision,"policy":a.policy_snapshot,
        "policy_layers":a.policy_layers,
    }


def grade_output(g):
    return {
        "id":str(g.pk),"enrollment":str(g.enrollment_id),
        "score":g.score,"feedback":g.feedback,
        "status":g.status,"percent":f"{g.percent:.6f}" if g.percent is not None else None,
        "label":g.label or None,"revision":g.revision,
    }


def exception_response(exc):
    if hasattr(exc,"message_dict"):
        messages=[x for group in exc.message_dict.values() for x in group]
    else:messages=exc.messages
    return JsonResponse({"error":" ".join(messages)[:500]},status=422)


@require_http_methods(["GET","POST"])
@authorized
def assessments(request,school_id,course_id):
    school,course,error=course_access(request,school_id,course_id,write=request.method=="POST")
    if error is not None:return error
    if request.method=="GET":
        return JsonResponse({"assessments":[serialize(a) for a in Assessment.objects.filter(school=school,course=course).order_by("-assessment_date","pk")[:300]]})
    data,error=parse_body(request)
    if error is not None:return error
    try:
        values=fields(data)
        if not course.active:raise ValueError("Le cours est archivé.")
        if not course.year.active or not course.classroom.active:raise ValueError("Année ou classe inactive.")
        period=values.get("period_id")
        if period is not None and not AcademicPeriod.objects.filter(school=school,year=course.year,pk=period,active=True).exists():
            raise ValueError("Période introuvable dans cette année.")
        level=course.classroom.level
        context={"year":course.year.code,"cycle":level.cycle.code,"level":level.code,"class":course.classroom.code}
        settings, layers=resolve_settings(school,context)
        policy=settings.get("grading")
        if policy is None:raise ValueError("Configurez d'abord un barème pour l'établissement, le cycle, le niveau ou la classe.")
        try:validate_policy(policy)
        except (PolicyError,TypeError,KeyError,AttributeError):raise ValueError("Le barème configuré est invalide.") from None
        with transaction.atomic():
            assessment=Assessment(school=school,course=course,policy_snapshot=policy,policy_layers=layers,**values)
            assessment.full_clean();assessment.save()
            log_event(school,request,"assessment_created",assessment.pk)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    except ValidationError as exc:return exception_response(exc)
    return JsonResponse(serialize(assessment),status=201)


@require_http_methods(["GET","PATCH"])
@authorized
def assessment_detail(request,school_id,assessment_id):
    school,obj,error=assessment_access(request,school_id,assessment_id,write=request.method=="PATCH")
    if error is not None:return error
    if request.method=="GET":return JsonResponse(serialize(obj))
    data,error=parse_body(request)
    if error is not None:return error
    try:clean=fields(data,updating=True)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    try:
        with transaction.atomic():
            obj=Assessment.objects.select_for_update().get(school=school,pk=assessment_id)
            if obj.published:return JsonResponse({"error":"Évaluation publiée et verrouillée."},status=409)
            if obj.revision!=data["revision"]:return JsonResponse({"error":"Conflit de version.","revision":obj.revision},status=409)
            for k,v in clean.items():setattr(obj,k,v)
            obj.full_clean();obj.revision+=1;obj.save()
            log_event(school,request,"assessment_updated",obj.pk)
    except ValidationError as exc:return exception_response(exc)
    return JsonResponse(serialize(obj))


@require_GET
@authorized
def roster(request,school_id,assessment_id):
    school,assessment,error=assessment_access(request,school_id,assessment_id)
    if error is not None:return error
    rows=Enrollment.objects.select_related("student").filter(
        school=school,year=assessment.course.year,classroom=assessment.course.classroom,active=True,
        student__active=True,
    ).order_by("student__last_name","student__first_name","pk")[:500]
    return JsonResponse({"students":[{
        "enrollment_id":str(e.pk),"student_code":e.student.student_code,
        "first_name":e.student.first_name,"last_name":e.student.last_name,
    } for e in rows]})


def verify_score(assessment,score):
    try:result=evaluate(assessment.policy_snapshot,[{"score":score,"weight":1}])
    except (PolicyError,TypeError,ValueError,OverflowError) as exc:
        raise ValueError("Note incompatible avec le barème de cette évaluation.") from exc
    return result


def grade_fields(data,updating=False):
    allowed={"score","feedback"} if updating else {"enrollment","score","feedback"}
    if set(data)-allowed-({"revision"} if updating else set()):raise ValueError("Champs inconnus.")
    if not updating and not {"enrollment","score"}<=set(data):raise ValueError("Élève et résultat obligatoires.")
    if updating and (type(data.get("revision")) is not int or data["revision"]<1 or len(data)==1):
        raise ValueError("Révision invalide.")
    fields={}
    for k,v in data.items():
        if k=="revision":continue
        if k=="enrollment":
            try:fields["enrollment_id"]=UUID(v)
            except (ValueError,TypeError,AttributeError):raise ValueError("Inscription invalide.") from None
        elif k=="feedback":
            if not isinstance(v,str) or len(v)>500:raise ValueError("Commentaire trop long.")
            fields[k]=v.strip()
        else:fields[k]=v
    return fields


@require_http_methods(["GET","POST"])
@authorized
def grades(request,school_id,assessment_id):
    school,assessment,error=assessment_access(request,school_id,assessment_id,write=request.method=="POST")
    if error is not None:return error
    if request.method=="GET":
        rows=AssessmentGrade.objects.filter(school=school,assessment=assessment).order_by("pk")[:500]
        return JsonResponse({"grades":[grade_output(g) for g in rows]})
    if assessment.published or not assessment.active:return JsonResponse({"error":"Évaluation verrouillée ou archivée."},status=409)
    data,error=parse_body(request)
    if error is not None:return error
    try:
        fields=grade_fields(data)
        enrollment=Enrollment.objects.filter(
            school=school,pk=fields["enrollment_id"],year=assessment.course.year,
            classroom=assessment.course.classroom,active=True,student__active=True,
        ).first()
        if enrollment is None:raise ValueError("Élève non inscrit dans cette classe.")
        result=verify_score(assessment,fields["score"])
        with transaction.atomic():
            locked=Assessment.objects.select_for_update().get(school=school,pk=assessment.pk)
            if locked.published or not locked.active:
                return JsonResponse({"error":"Évaluation verrouillée ou archivée."},status=409)
            grade=AssessmentGrade(school=school,assessment=assessment,enrollment=enrollment,
                author=request.user,score=fields["score"],feedback=fields.get("feedback",""),
                status=result["status"],percent=result["percent"],label=result["label"] or "")
            grade.full_clean();grade.save()
            log_event(school,request,"grade_created",grade.pk)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    except ValidationError as exc:return exception_response(exc)
    return JsonResponse(grade_output(grade),status=201)


@require_http_methods(["GET","PATCH"])
@authorized
def grade_detail(request,school_id,assessment_id,grade_id):
    school,assessment,error=assessment_access(request,school_id,assessment_id,write=request.method=="PATCH")
    if error is not None:return error
    obj=AssessmentGrade.objects.filter(school=school,assessment=assessment,pk=grade_id).first()
    if obj is None:return JsonResponse({"error":"Note introuvable."},status=404)
    if request.method=="GET":return JsonResponse(grade_output(obj))
    if assessment.published or not assessment.active:return JsonResponse({"error":"Évaluation verrouillée ou archivée."},status=409)
    data,error=parse_body(request)
    if error is not None:return error
    try:
        values=grade_fields(data,updating=True)
        result=verify_score(assessment,values["score"]) if "score" in values else None
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    try:
        with transaction.atomic():
            locked=Assessment.objects.select_for_update().get(school=school,pk=assessment.pk)
            if locked.published or not locked.active:
                return JsonResponse({"error":"Évaluation verrouillée ou archivée."},status=409)
            grade=AssessmentGrade.objects.select_for_update().get(school=school,assessment=assessment,pk=grade_id)
            if grade.revision!=data["revision"]:return JsonResponse({"error":"Conflit de version.","revision":grade.revision},status=409)
            for k,v in values.items():setattr(grade,k,v)
            if result is not None:
                grade.status=result["status"];grade.percent=result["percent"];grade.label=result["label"] or ""
            grade.full_clean();grade.revision+=1;grade.author=request.user;grade.save()
            log_event(school,request,"grade_updated",grade.pk)
    except ValidationError as exc:return exception_response(exc)
    return JsonResponse(grade_output(grade))


@require_http_methods(["POST"])
@authorized
def grade_batch(request, school_id, assessment_id):
    """Save a mobile gradebook atomically: all valid changes or none."""
    school, assessment, error = assessment_access(request, school_id, assessment_id, write=True)
    if error is not None:
        return error
    body, error = parse_body(request)
    if error is not None:
        return error
    if (not isinstance(body, dict) or set(body) != {"grades"} or
            not isinstance(body["grades"], list) or not 1 <= len(body["grades"]) <= 100):
        return JsonResponse({"error": "Lot invalide : entre 1 et 100 notes."}, status=422)

    try:
        rows = []
        seen = set()
        for entry in body["grades"]:
            if not isinstance(entry, dict) or set(entry) != {"enrollment", "score", "revision"}:
                raise ValueError("Champs de note invalides.")
            try:
                if not isinstance(entry["enrollment"], str):
                    raise ValueError()
                enrollment_id = UUID(entry["enrollment"])
            except (TypeError, ValueError, AttributeError):
                raise ValueError("Identifiant d'inscription invalide.") from None
            if enrollment_id in seen:
                raise ValueError("Inscription répétée dans le lot.")
            seen.add(enrollment_id)
            revision = entry["revision"]
            if type(revision) is not int or revision < 0:
                raise ValueError("Révision de note invalide.")
            result = verify_score(assessment, entry["score"])
            rows.append((enrollment_id, entry["score"], revision, result))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)

    try:
        with transaction.atomic():
            locked = Assessment.objects.select_for_update().get(school=school, pk=assessment.pk)
            if locked.published or not locked.active:
                return JsonResponse({"error": "Évaluation publiée ou archivée."}, status=409)
            if not locked.course.active or not locked.course.year.active:
                return JsonResponse({"error": "Cours ou année inactive."}, status=409)
            allowed = set(Enrollment.objects.filter(
                school=school, pk__in=seen, year=locked.course.year,
                classroom=locked.course.classroom, active=True, student__active=True,
            ).values_list("pk", flat=True))
            if allowed != seen:
                return JsonResponse({"error": "Inscription hors de la classe autorisée."}, status=422)
            previous = {
                item.enrollment_id: item for item in AssessmentGrade.objects.select_for_update().filter(
                    school=school, assessment=locked, enrollment_id__in=seen,
                )
            }
            # Validate every revision before writing anything.
            for enrollment_id, _score, revision, _result in rows:
                current = previous.get(enrollment_id)
                if revision != (current.revision if current else 0):
                    return JsonResponse({"error": "Conflit de version : rechargez les notes.",
                                         "enrollment": str(enrollment_id)}, status=409)
            output = []
            for enrollment_id, score, _revision, result in rows:
                grade = previous.get(enrollment_id)
                if grade is None:
                    grade = AssessmentGrade(school=school, assessment=locked,
                                            enrollment_id=enrollment_id, author=request.user)
                else:
                    grade.revision += 1
                    grade.author = request.user
                grade.score = score
                grade.status = result["status"]
                grade.percent = result["percent"]
                grade.label = result["label"] or ""
                grade.full_clean()
                grade.save()
                output.append(grade_output(grade))
            log_event(school, request, "grades_batch_saved", locked.pk)
    except ValidationError as exc:
        return exception_response(exc)
    return JsonResponse({"grades": output, "saved": len(output)})


@require_GET
@authorized
def course_averages(request, school_id, course_id):
    """Provisional weighted subject averages based on *each saved grading snapshot*.

    Missing entries are excluded, not counted as zeros. Results are normalized from
    the underlying grading policy percentages (numeric, letters, competencies).
    They are not a published bulletin or a definitive class ranking.
    """
    school, course, error = course_access(request, school_id, course_id)
    if error is not None:
        return error
    period_id = request.GET.get("period", "")
    if period_id:
        try:
            period_key = UUID(period_id)
        except (ValueError, AttributeError, TypeError):
            return JsonResponse({"error": "Période invalide."}, status=422)
        if not AcademicPeriod.objects.filter(
            school=school, year=course.year, pk=period_key,
        ).exists():
            return JsonResponse({"error": "Période hors du cours."}, status=422)
    else:
        period_key = None
    assessments = list(Assessment.objects.filter(
        school=school, course=course, active=True,
    ).filter(**({"period_id": period_key} if period_key else {})).order_by(
        "assessment_date", "pk",
    )[:300])
    enrollments = list(Enrollment.objects.select_related("student").filter(
        school=school, year=course.year, classroom=course.classroom,
        active=True, student__active=True,
    ).order_by("student__last_name", "student__first_name", "pk")[:500])
    assessed = {a.pk: a for a in assessments}
    points = {}
    for grade in AssessmentGrade.objects.filter(
        school=school, assessment_id__in=assessed,
        enrollment_id__in=[e.pk for e in enrollments],
        status="calculated", percent__isnull=False,
    ):
        weight = assessed[grade.assessment_id].weight
        item = points.setdefault(grade.enrollment_id, [Decimal("0"), Decimal("0"), 0])
        item[0] += grade.percent * weight
        item[1] += weight
        item[2] += 1
    output = []
    for enrollment in enrollments:
        value = points.get(enrollment.pk)
        avg = (value[0] / value[1]) if value and value[1] else None
        on_twenty = (avg / Decimal("5")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if avg is not None else None
        output.append({
            "enrollment": str(enrollment.pk),
            "student_code": enrollment.student.student_code,
            "first_name": enrollment.student.first_name,
            "last_name": enrollment.student.last_name,
            "evaluated": value[2] if value else 0,
            "expected": len(assessments),
            "complete": bool(value and len(assessments) and value[2] == len(assessments)),
            "average_percent": str(avg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if avg is not None else None,
            "average_on_20": str(on_twenty) if on_twenty is not None else None,
        })
    values = [Decimal(row["average_on_20"]) for row in output if row["average_on_20"] is not None]
    class_average = (sum(values) / len(values)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    ) if values else None
    return JsonResponse({
        "course": str(course.pk), "period": str(period_key) if period_key else None,
        "assessment_count": len(assessments), "student_count": len(output),
        "class_average_on_20": str(class_average) if class_average is not None else None,
        "calculated_count": len(values),
        "students": output,
        "provisional": True,
    })
