"""Calculate a printable report from published assessments without a fixed national scale."""
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from pedagogy.domain import validate_policy, ValidationError as PolicyError
from .services import resolve_settings
from .curriculum_models import CourseOffering
from .assessment_models import Assessment, AssessmentGrade


def rounded(value,precision):
    return str(value.quantize(Decimal(10)**-precision,rounding=ROUND_HALF_UP))


def display_result(percent,policy,precision):
    if percent is None:
        return {"status":"empty","percent":None,"score":None,"label":None}
    bands=sorted(policy["bands"],key=lambda band:band["min"],reverse=True)
    label=next((band["label"] for band in bands if percent>=Decimal(str(band["min"]))),None)
    scale=policy["scale"]
    score=None
    if scale["kind"] in ("numeric","percentage"):
        maximum=Decimal(str(scale["max"] if scale["kind"]=="numeric" else 100))
        score=rounded(percent*maximum/100,precision)
    return {"status":"calculated","percent":rounded(percent,precision),"score":score,"label":label}


def report_configuration(values,grading):
    settings=values.get("bulletin",{})
    if not isinstance(settings,dict):raise ValueError("Configuration bulletin invalide.")
    allowed={"title","precision","show_score","show_label","show_rank","missing_entry"}
    if set(settings)-allowed:raise ValueError("Option bulletin inconnue.")
    title=settings.get("title","Bulletin scolaire")
    precision=settings.get("precision",grading["precision"])
    show_score=settings.get("show_score",grading["report"]["showScore"])
    show_label=settings.get("show_label",grading["report"]["showLabel"])
    show_rank=settings.get("show_rank",False)
    missing=settings.get("missing_entry","exclude")
    if not isinstance(title,str) or not 1<=len(title.strip())<=120:raise ValueError("Titre de bulletin invalide.")
    if type(precision) is not int or not 0<=precision<=4:raise ValueError("Précision invalide.")
    if type(show_score) is not bool or type(show_label) is not bool or not (show_score or show_label):
        raise ValueError("Affichage de bulletin invalide.")
    if type(show_rank) is not bool:raise ValueError("Classement invalide.")
    if show_rank:raise ValueError("Le classement exige la validation collective du module de délibération.")
    if missing not in ("exclude","zero"):raise ValueError("Traitement des notes non saisies invalide.")
    return {
        "title":title.strip(),"precision":precision,
        "show_score":show_score,"show_label":show_label,
        "show_rank":False,"missing_entry":missing,
    }


def calculate_report(school,enrollment,period):
    classroom=enrollment.classroom
    level=classroom.level
    context={"year":enrollment.year.code,"cycle":level.cycle.code,"level":level.code,"class":classroom.code}
    settings,layers=resolve_settings(school,context)
    grading=settings.get("grading")
    if grading is None:raise ValueError("Aucun barème institutionnel configuré.")
    try:validate_policy(grading)
    except (PolicyError,TypeError,AttributeError,KeyError):raise ValueError("Barème de bulletin invalide.") from None
    opts=report_configuration(settings,grading)
    precision=opts["precision"]
    subjects=[]
    overall_sum=Decimal("0");overall_weight=Decimal("0")
    source_ids=[]
    recorded_grades=0
    qs=CourseOffering.objects.select_related("subject").filter(
        school=school,year=enrollment.year,classroom=classroom
    ).order_by("subject__name","pk")[:250]
    for course in qs:
        assessments=Assessment.objects.filter(
            school=school,course=course,published=True,
        )
        if period is not None:
            assessments=assessments.filter(period=period)
        assessments=list(assessments.order_by("assessment_date","pk")[:250])
        if not assessments:
            continue
        grades={g.assessment_id:g for g in AssessmentGrade.objects.filter(
            school=school,enrollment=enrollment,assessment__in=assessments
        )}
        total=Decimal("0");weight_sum=Decimal("0")
        for assessment in assessments:
            grade=grades.get(assessment.pk)
            contribution=None
            if grade is not None and grade.percent is not None:
                recorded_grades+=1
                contribution=Decimal(str(grade.percent))
            elif grade is None and opts["missing_entry"]=="zero":
                contribution=Decimal("0")
            if contribution is not None:
                total+=contribution*assessment.weight
                weight_sum+=assessment.weight
            source_ids.append({
                "assessment":str(assessment.pk),"revision":assessment.revision,
                "grade":str(grade.pk) if grade else None,
                "grade_revision":grade.revision if grade else None,
            })
        percent=total/weight_sum if weight_sum else None
        result=display_result(percent,grading,precision)
        item={
            "course":str(course.pk),"subject":course.subject.name,
            "coefficient":str(course.coefficient),
            "result":result,"assessments":len(assessments),
        }
        subjects.append(item)
        if percent is not None:
            overall_sum+=percent*course.coefficient
            overall_weight+=course.coefficient
    overall_percent=overall_sum/overall_weight if overall_weight else None
    return {
        "created_at":timezone.now().isoformat(),
        "school":{"id":str(school.pk),"name":school.name,"short_name":school.short_name},
        "student":{"id":str(enrollment.student_id),"code":enrollment.student.student_code,
                   "first_name":enrollment.student.first_name,"last_name":enrollment.student.last_name},
        "class":{"id":str(classroom.pk),"name":classroom.name},
        "year":{"id":str(enrollment.year_id),"name":enrollment.year.name},
        "period":{"id":str(period.pk),"name":period.name} if period else None,
        "subjects":subjects,
        "overall":display_result(overall_percent,grading,precision),
        "policy_snapshot":grading,
        "template":opts,
        "layers":layers,
        "sources":source_ids,
        "recorded_grade_count":recorded_grades,
    }
