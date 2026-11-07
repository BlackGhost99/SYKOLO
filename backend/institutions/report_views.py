"""Draft/published report cards with auditable snapshots and A4 PDF export."""
from io import BytesIO
from uuid import UUID
from html import escape
from django.db import transaction, IntegrityError
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import authorized
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

from .views import access, refuse, parse_body, log_event
from .services import has_permission
from .academic_models import AcademicPeriod
from .assessment_models import Assessment
from .student_models import Enrollment
from .report_models import SchoolReport
from .report_engine import calculate_report


def permission(request,school_id,name):
    school,error=access(request,school_id)
    if error is not None:return None,error
    if not has_permission(request.user,school,name):return None,refuse()
    return school,None


def find_report(request,school_id,report_id,name):
    school,error=permission(request,school_id,name)
    if error is not None:return None,None,error
    report=SchoolReport.objects.filter(school=school,pk=report_id).first()
    if report is None:return None,None,JsonResponse({"error":"Bulletin introuvable."},status=404)
    return school,report,None


def load_enrollment(school,data):
    try:uid=UUID(data["enrollment"])
    except (KeyError,TypeError,ValueError,AttributeError):raise ValueError("Inscription invalide.") from None
    enrollment=Enrollment.objects.select_related("student","classroom__level__cycle","year").filter(school=school,pk=uid).first()
    if enrollment is None:raise ValueError("Inscription inconnue dans cet établissement.")
    return enrollment


def load_period(school,year,data):
    if data.get("period") is None:return None
    try:uid=UUID(data["period"])
    except (TypeError,ValueError,AttributeError):raise ValueError("Période invalide.") from None
    period=AcademicPeriod.objects.filter(school=school,year=year,pk=uid).first()
    if period is None:raise ValueError("Période inconnue dans l'année scolaire.")
    return period


def report_output(r,include_snapshot=False):
    result={
        "id":str(r.pk),"enrollment":str(r.enrollment_id),
        "year":str(r.year_id),"period":str(r.period_id) if r.period_id else None,
        "status":r.status,"revision":r.revision,
        "published_at":r.published_at.isoformat() if r.published_at else None,
    }
    if include_snapshot:result["snapshot"]=r.snapshot
    return result


@require_http_methods(["GET","POST"])
@authorized
def reports(request,school_id):
    action="school.reports.read" if request.method=="GET" else "school.reports.manage"
    school,error=permission(request,school_id,action)
    if error is not None:return error
    if request.method=="GET":
        rows=SchoolReport.objects.filter(school=school).order_by("-created_at","pk")[:250]
        return JsonResponse({"reports":[report_output(r) for r in rows]})
    data,error=parse_body(request)
    if error is not None:return error
    if set(data)-{"enrollment","period","revision"}:
        return JsonResponse({"error":"Champs inconnus."},status=422)
    rev=data.get("revision")
    if type(rev) is not int or rev<0:return JsonResponse({"error":"Révision attendue."},status=422)
    try:
        enrollment=load_enrollment(school,data)
        period=load_period(school,enrollment.year,data)
        key=str(period.pk) if period else ""
        with transaction.atomic():
            existing=SchoolReport.objects.select_for_update().filter(
                school=school,enrollment=enrollment,year=enrollment.year,period_key=key
            ).first()
            if existing:
                if existing.status=="published":return JsonResponse({"error":"Bulletin déjà publié et immuable."},status=409)
                if existing.revision!=rev:return JsonResponse({"error":"Conflit de version.","revision":existing.revision},status=409)
            elif rev!=0:
                return JsonResponse({"error":"Conflit de version.","revision":0},status=409)
            snapshot=calculate_report(school,enrollment,period)
            if existing:
                existing.snapshot=snapshot;existing.revision+=1
                existing.prepared_by=request.user
                existing.full_clean();existing.save()
                report=existing
            else:
                report=SchoolReport(
                    school=school,enrollment=enrollment,year=enrollment.year,
                    period=period,period_key=key,snapshot=snapshot,prepared_by=request.user,
                )
                report.full_clean();report.save()
            log_event(school,request,"report_refreshed" if existing else "report_created",report.pk)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    except IntegrityError:return JsonResponse({"error":"Bulletin déjà présent ; actualisez sa version."},status=409)
    return JsonResponse(report_output(report,True),status=200 if existing else 201)


@require_GET
@authorized
def report_detail(request,school_id,report_id):
    school,r,error=find_report(request,school_id,report_id,"school.reports.read")
    if error is not None:return error
    return JsonResponse(report_output(r,True))


@require_POST
@authorized
def publish_report(request,school_id,report_id):
    school,r,error=find_report(request,school_id,report_id,"school.reports.publish")
    if error is not None:return error
    data,error=parse_body(request)
    if error is not None:return error
    if set(data)!={"revision"} or type(data["revision"]) is not int:return JsonResponse({"error":"Révision requise."},status=422)
    with transaction.atomic():
        r=SchoolReport.objects.select_for_update().get(school=school,pk=report_id)
        if r.status=="published":return JsonResponse({"error":"Bulletin déjà publié."},status=409)
        if r.revision!=data["revision"]:return JsonResponse({"error":"Conflit de version.","revision":r.revision},status=409)
        if r.snapshot.get("recorded_grade_count",0)<1 or r.snapshot.get("overall",{}).get("status")!="calculated":
            return JsonResponse({"error":"Aucun résultat calculé, publication impossible."},status=422)
        r.status="published";r.published_at=timezone.now();r.revision+=1;r.save(update_fields=["status","published_at","revision"])
        log_event(school,request,"report_published",r.pk)
    return JsonResponse(report_output(r,True))


@require_POST
@authorized
def publish_assessment(request,school_id,assessment_id):
    school,error=permission(request,school_id,"school.reports.publish")
    if error is not None:return error
    data,error=parse_body(request)
    if error is not None:return error
    if set(data)!={"revision"} or type(data["revision"]) is not int:return JsonResponse({"error":"Révision requise."},status=422)
    with transaction.atomic():
        a=Assessment.objects.select_for_update().filter(school=school,pk=assessment_id).first()
        if a is None:return JsonResponse({"error":"Évaluation introuvable."},status=404)
        if a.published:return JsonResponse({"error":"Déjà publiée."},status=409)
        if not a.active:return JsonResponse({"error":"Évaluation archivée."},status=409)
        if a.revision!=data["revision"]:return JsonResponse({"error":"Conflit de version.","revision":a.revision},status=409)
        a.published=True;a.revision+=1;a.save(update_fields=["published","revision"])
        log_event(school,request,"assessment_published",a.pk)
    return JsonResponse({"id":str(a.pk),"published":True,"revision":a.revision})


def pdf_bytes(r):
    data=r.snapshot
    stream=BytesIO()
    doc=SimpleDocTemplate(stream,pagesize=A4,rightMargin=17*mm,leftMargin=17*mm,
        topMargin=14*mm,bottomMargin=15*mm)
    style=getSampleStyleSheet()
    normal=ParagraphStyle("YemNormal",parent=style["Normal"],fontName="Helvetica",fontSize=9,leading=13)
    header=ParagraphStyle("YemHeader",parent=style["Heading1"],fontName="Helvetica-Bold",fontSize=15,leading=19,alignment=TA_CENTER)
    story=[
        Paragraph(escape(data["school"]["name"]),header),
        Spacer(1,4*mm),
        Paragraph(escape(data["template"]["title"]),header),
        Spacer(1,5*mm),
    ]
    status="PUBLIÉ" if r.status=="published" else "BROUILLON — NON OFFICIEL"
    labels=[
        f"{data['student']['last_name']} {data['student']['first_name']} ({data['student']['code']})",
        f"Classe : {data['class']['name']} | Année : {data['year']['name']}",
        f"Période : {data['period']['name'] if data['period'] else 'Année entière'}",
        status,
    ]
    identity = data["student"].get("matricule_yem")
    if identity and identity != data["student"]["code"]:
        labels.insert(1, "Identifiant permanent YEM : " + identity)
    if data.get("amendment"):
        labels.append("RECTIFICATIF N° " + str(data["amendment"]["sequence"]) + " — original conservé")
        labels.append("Motif : " + data["amendment"]["reason"])
    for label in labels:story.append(Paragraph(escape(label),normal))
    story.append(Spacer(1,5*mm))
    def p(value):return Paragraph(escape(str(value)),normal)
    table_data=[[p("Matière"),p("Coefficient"),p("Résultat")]]
    for item in data["subjects"]:
        result=item["result"]
        displayed=[]
        if data["template"]["show_score"] and result["score"] is not None:displayed.append(result["score"])
        if data["template"]["show_label"] and result["label"]:displayed.append(result["label"])
        if not displayed:displayed=["Non évalué"]
        table_data.append([p(item["subject"]),p(item["coefficient"]),p(" · ".join(displayed))])
    if len(table_data)==1:table_data.append([p("Aucune évaluation publiée"),p("—"),p("—")])
    table=Table(table_data,colWidths=[88*mm,30*mm,56*mm],repeatRows=1,hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F0F0F0")),
        ("LINEBELOW",(0,0),(-1,0),0.7,colors.HexColor("#555555")),
        ("LINEBELOW",(0,1),(-1,-1),0.25,colors.HexColor("#DDDDDD")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),5),
        ("RIGHTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    story.append(table);story.append(Spacer(1,6*mm))
    overall=data["overall"]
    overall_display=[]
    if data["template"]["show_score"] and overall["score"] is not None:overall_display.append(overall["score"])
    if data["template"]["show_label"] and overall["label"]:overall_display.append(overall["label"])
    story.append(Paragraph("Résultat général : "+escape(" · ".join(overall_display) or "Non calculé"),normal))
    story.append(Spacer(1,10*mm))
    story.append(Paragraph("Généré par YEM — Document scolaire",normal))
    doc.build(story)
    return stream.getvalue()


@require_GET
@authorized
def report_pdf(request,school_id,report_id):
    school,r,error=find_report(request,school_id,report_id,"school.reports.read")
    if error is not None:return error
    blob=pdf_bytes(r)
    response=HttpResponse(blob,content_type="application/pdf")
    response["Content-Disposition"]=f'attachment; filename="yem-bulletin-{str(r.pk)[:8]}.pdf"'
    response["Cache-Control"]="private, no-store"
    return response
