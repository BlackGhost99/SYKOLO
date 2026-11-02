"""Module 10: conseils scolaires, décisions configurables et rectifications auditables."""
import copy
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from uuid import UUID

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from accounts.views import authorized

from .academic_models import AcademicClass, AcademicPeriod
from .council_models import SchoolCouncil, CouncilDecision, ReportAmendment
from .report_models import SchoolReport
from .report_engine import display_result, rounded
from .report_views import pdf_bytes
from .student_models import Enrollment
from .services import has_permission, resolve_settings
from .views import access, refuse, parse_body, log_event


def uid(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def gate(request, school_id, permission):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, permission):
        return None, refuse()
    return school, None


def council_data(c):
    return {"id":str(c.pk), "year":str(c.year_id), "classroom":str(c.classroom_id),
        "period":str(c.period_id) if c.period_id else None, "title":c.title,
        "meeting_date":c.meeting_date.isoformat(), "status":c.status, "revision":c.revision,
        "closed_at":c.closed_at.isoformat() if c.closed_at else None}


def decision_data(d):
    return {"id":str(d.pk), "enrollment":str(d.enrollment_id), "report":str(d.report_id),
        "code":d.code, "label":d.label, "rationale":d.rationale, "revision":d.revision}


def choices(school, classroom):
    context={"year":classroom.year.code, "cycle":classroom.level.cycle.code,
        "level":classroom.level.code, "class":classroom.code}
    config=resolve_settings(school,context)[0].get("deliberation",{})
    if not isinstance(config,dict) or set(config)-{"decisions"}:
        raise ValueError("Configuration des décisions invalide.")
    options=config.get("decisions",[])
    if not isinstance(options,list) or len(options)>30:
        raise ValueError("Catalogue des décisions invalide.")
    found={}
    for entry in options:
        if not isinstance(entry,dict) or set(entry)!={"code","label"}:
            raise ValueError("Format de décision invalide.")
        code,label=entry["code"],entry["label"]
        if not isinstance(code,str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,47}",code):
            raise ValueError("Code de décision invalide.")
        if not isinstance(label,str) or not 1<=len(label.strip())<=120 or code in found:
            raise ValueError("Libellé ou doublon de décision invalide.")
        found[code]=label.strip()
    return found


@require_GET
@authorized
def council_choices(request,school_id):
    school,error=gate(request,school_id,"school.deliberations.read")
    if error is not None:return error
    classroom=AcademicClass.objects.select_related("year","level__cycle").filter(
        school=school,pk=uid(request.GET.get("classroom"))).first()
    if not classroom:return JsonResponse({"error":"Classe introuvable."},status=404)
    try:configured=choices(school,classroom)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    return JsonResponse({"decisions":[{"code":c,"label":l} for c,l in configured.items()]})


@require_http_methods(["GET","POST"])
@authorized
def councils(request,school_id):
    perm="school.deliberations.read" if request.method=="GET" else "school.deliberations.manage"
    school,error=gate(request,school_id,perm)
    if error is not None:return error
    if request.method=="GET":
        return JsonResponse({"councils":[council_data(c) for c in SchoolCouncil.objects.filter(
            school=school).order_by("-meeting_date","pk")[:250]]})
    data,error=parse_body(request)
    if error is not None:return error
    if set(data)!={"classroom","period","title","meeting_date"}:
        return JsonResponse({"error":"Champs de conseil invalides."},status=422)
    classroom=AcademicClass.objects.select_related("year","level__cycle").filter(
        school=school,pk=uid(data["classroom"]),active=True).first()
    if classroom is None:return JsonResponse({"error":"Classe introuvable."},status=404)
    period=None
    if data["period"] is not None:
        period=AcademicPeriod.objects.filter(school=school,year=classroom.year,pk=uid(data["period"])).first()
        if period is None:return JsonResponse({"error":"Période non rattachée à cette année."},status=422)
    title=data["title"]
    if not isinstance(title,str) or not 1<=len(title.strip())<=140:
        return JsonResponse({"error":"Titre invalide."},status=422)
    try:
        meeting=date.fromisoformat(data["meeting_date"])
        if meeting.isoformat()!=data["meeting_date"]:raise ValueError()
    except (ValueError,TypeError):
        return JsonResponse({"error":"Date invalide."},status=422)
    try:
        with transaction.atomic():
            obj=SchoolCouncil(school=school,year=classroom.year,classroom=classroom,period=period,
                period_key=str(period.pk) if period else "",title=title.strip(),meeting_date=meeting,
                created_by=request.user)
            obj.full_clean()
            obj.save()
            log_event(school,request,"council_created",obj.pk)
    except ValidationError as exc:
        return JsonResponse({"error":str(exc)},status=422)
    except IntegrityError:
        return JsonResponse({"error":"Ce conseil existe déjà."},status=409)
    return JsonResponse(council_data(obj),status=201)


@require_GET
@authorized
def council_detail(request,school_id,council_id):
    school,error=gate(request,school_id,"school.deliberations.read")
    if error is not None:return error
    council=SchoolCouncil.objects.filter(school=school,pk=council_id).first()
    if council is None:return JsonResponse({"error":"Conseil introuvable."},status=404)
    return JsonResponse({**council_data(council),
        "decisions":[decision_data(d) for d in council.decisions.order_by("pk")]})


@require_POST
@authorized
def council_decisions(request,school_id,council_id):
    school,error=gate(request,school_id,"school.deliberations.manage")
    if error is not None:return error
    data,error=parse_body(request)
    if error is not None:return error
    if set(data)!={"enrollment","report","code","rationale","revision"} or type(data["revision"]) is not int or data["revision"]<0:
        return JsonResponse({"error":"Données de décision invalides."},status=422)
    reason=data["rationale"]
    if not isinstance(reason,str) or not 1<=len(reason.strip())<=1000 or not isinstance(data["code"],str):
        return JsonResponse({"error":"Motif ou code invalide."},status=422)
    with transaction.atomic():
        council=SchoolCouncil.objects.select_for_update().select_related(
            "classroom__year","classroom__level__cycle").filter(school=school,pk=council_id).first()
        if council is None:return JsonResponse({"error":"Conseil introuvable."},status=404)
        if council.status!="draft":return JsonResponse({"error":"Conseil clôturé."},status=409)
        try:catalog=choices(school,council.classroom)
        except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
        if data["code"] not in catalog:return JsonResponse({"error":"Décision non configurée."},status=422)
        enrollment=Enrollment.objects.filter(school=school,pk=uid(data["enrollment"]),
            year=council.year,classroom=council.classroom,active=True).first()
        if enrollment is None:return JsonResponse({"error":"Inscription hors classe."},status=404)
        report=SchoolReport.objects.filter(school=school,pk=uid(data["report"]),
            enrollment=enrollment,period=council.period,status="published").first()
        if report is None:return JsonResponse({"error":"Bulletin publié correspondant requis."},status=422)
        existing=CouncilDecision.objects.select_for_update().filter(council=council,enrollment=enrollment).first()
        revision=existing.revision if existing else 0
        if data["revision"]!=revision:
            return JsonResponse({"error":"Conflit de version.","revision":revision},status=409)
        if existing:
            existing.report=report
            existing.code=data["code"]
            existing.label=catalog[data["code"]]
            existing.rationale=reason.strip()
            existing.decided_by=request.user
            existing.revision+=1
            existing.full_clean()
            existing.save()
            item=existing
        else:
            item=CouncilDecision(school=school,council=council,enrollment=enrollment,
                report=report,code=data["code"],label=catalog[data["code"]],
                rationale=reason.strip(),decided_by=request.user)
            item.full_clean()
            item.save()
        council.revision+=1
        council.save(update_fields=["revision"])
        log_event(school,request,"council_decision_saved",item.pk)
    return JsonResponse(decision_data(item),status=200 if existing else 201)


@require_POST
@authorized
def close_council(request,school_id,council_id):
    school,error=gate(request,school_id,"school.deliberations.finalize")
    if error is not None:return error
    data,error=parse_body(request)
    if error is not None:return error
    if set(data)!={"revision"} or type(data["revision"]) is not int or data["revision"]<1:
        return JsonResponse({"error":"Révision obligatoire."},status=422)
    with transaction.atomic():
        council=SchoolCouncil.objects.select_for_update().filter(school=school,pk=council_id).first()
        if council is None:return JsonResponse({"error":"Conseil introuvable."},status=404)
        if council.status=="closed":return JsonResponse({"error":"Conseil déjà clôturé."},status=409)
        if council.revision!=data["revision"]:
            return JsonResponse({"error":"Conflit de version.","revision":council.revision},status=409)
        if not council.decisions.exists():return JsonResponse({"error":"Aucune décision."},status=422)
        council.status="closed"
        council.closed_at=timezone.now()
        council.closed_by=request.user
        council.revision+=1
        council.save(update_fields=["status","closed_at","closed_by","revision"])
        log_event(school,request,"council_closed",council.pk)
    return JsonResponse(council_data(council))


def amend_data(a):
    return {"id":str(a.pk),"report":str(a.report_id),"sequence":a.sequence,"course":str(a.course_id),
        "before_percent":a.previous_percent or None,"after_percent":a.corrected_percent,
        "reason":a.reason,"created_at":a.created_at.isoformat(),
        "actor_id":str(a.created_by_id) if a.created_by_id else None}


@require_http_methods(["GET","POST"])
@authorized
def amendments(request,school_id,report_id):
    permission="school.reports.read" if request.method=="GET" else "school.reports.amend"
    school,error=gate(request,school_id,permission)
    if error is not None:return error
    if request.method=="GET":
        if not SchoolReport.objects.filter(school=school,pk=report_id).exists():
            return JsonResponse({"error":"Bulletin introuvable."},status=404)
        return JsonResponse({"amendments":[amend_data(r) for r in ReportAmendment.objects.filter(
            school=school,report_id=report_id).order_by("sequence")[:100]]})
    data,error=parse_body(request)
    if error is not None:return error
    if set(data)!={"course","percent","reason","revision"} or type(data["revision"]) is not int or data["revision"]<0:
        return JsonResponse({"error":"Rectification invalide."},status=422)
    course=uid(data["course"])
    reason=data["reason"]
    value=data["percent"]
    if course is None or not isinstance(reason,str) or not 10<=len(reason.strip())<=1000:
        return JsonResponse({"error":"Matière ou justification invalide."},status=422)
    if isinstance(value,bool) or not isinstance(value,(int,float,str)):
        return JsonResponse({"error":"Pourcentage invalide."},status=422)
    try:
        percent=Decimal(str(value))
        if not percent.is_finite() or not Decimal("0")<=percent<=Decimal("100"):
            raise ValueError()
    except (InvalidOperation,ValueError):
        return JsonResponse({"error":"Pourcentage hors de 0 à 100."},status=422)
    with transaction.atomic():
        report=SchoolReport.objects.select_for_update().filter(school=school,pk=report_id).first()
        if report is None:return JsonResponse({"error":"Bulletin introuvable."},status=404)
        if report.status!="published":return JsonResponse({"error":"Bulletin non publié."},status=409)
        last=ReportAmendment.objects.filter(school=school,report=report).order_by("-sequence").first()
        rev=last.sequence if last else 0
        if data["revision"]!=rev:
            return JsonResponse({"error":"Conflit de version.","revision":rev},status=409)
        prior=copy.deepcopy(last.snapshot if last else report.snapshot)
        snapshot=copy.deepcopy(prior)
        subject=next((x for x in snapshot.get("subjects",[]) if x.get("course")==str(course)),None)
        if subject is None:return JsonResponse({"error":"Cours absent du bulletin."},status=422)
        policy=snapshot["policy_snapshot"]
        precision=snapshot["template"]["precision"]
        before=subject["result"]["percent"]
        subject["result"]=display_result(percent,policy,precision)
        total=Decimal("0");weight=Decimal("0")
        for x in snapshot["subjects"]:
            if x["result"]["percent"] is not None:
                coeff=Decimal(str(x["coefficient"]))
                total+=Decimal(str(x["result"]["percent"]))*coeff
                weight+=coeff
        snapshot["overall"]=display_result(total/weight if weight else None,policy,precision)
        snapshot["amendment"]={"sequence":rev+1,"reason":reason.strip(),"course":str(course),
            "before_percent":before,"after_percent":rounded(percent,precision),
            "recorded_at":timezone.now().isoformat()}
        row=ReportAmendment(school=school,report=report,sequence=rev+1,course_id=course,
            previous_percent=before or "",corrected_percent=rounded(percent,precision),
            reason=reason.strip(),prior_snapshot=prior,snapshot=snapshot,created_by=request.user)
        row.full_clean()
        row.save()
        log_event(school,request,"report_amendment_created",row.pk)
    return JsonResponse({**amend_data(row),"snapshot":row.snapshot},status=201)


@require_GET
@authorized
def amendment_detail(request,school_id,report_id,amendment_id):
    school,error=gate(request,school_id,"school.reports.read")
    if error is not None:return error
    item=ReportAmendment.objects.filter(school=school,report_id=report_id,pk=amendment_id).first()
    if item is None:return JsonResponse({"error":"Rectificatif introuvable."},status=404)
    return JsonResponse({**amend_data(item),"snapshot":item.snapshot})


@require_GET
@authorized
def amendment_pdf(request,school_id,report_id,amendment_id):
    school,error=gate(request,school_id,"school.reports.read")
    if error is not None:return error
    item=ReportAmendment.objects.select_related("report").filter(
        school=school,report_id=report_id,pk=amendment_id).first()
    if item is None:return JsonResponse({"error":"Rectificatif introuvable."},status=404)
    copy_report=SimpleNamespace(snapshot=item.snapshot,status="published",pk=item.report_id)
    response=HttpResponse(pdf_bytes(copy_report),content_type="application/pdf")
    response["Content-Disposition"]=f'attachment; filename="yem-rectificatif-{item.sequence}.pdf"'
    response["Cache-Control"]="private, no-store"
    return response
