"""Staff management for authorized administrators; private employee information."""
import re
from datetime import date
from uuid import UUID, uuid4
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET
from accounts.views import authorized
from .views import access, refuse, parse_body, log_event
from .services import has_permission
from .cycle_scope import scoped_cycle_ids
from .models import SchoolMember
from .academic_models import AcademicYear, AcademicClass
from .staff_models import StaffRecord, StaffAssignment
from .staff_profile_models import StaffProfile


def scope(request, school_id, action):
    school, error=access(request,school_id)
    if error is not None: return None,error
    if not has_permission(request.user,school,action): return None,refuse()
    return school,None


def parse_staff(data, *, editing=False):
    allowed={"staff_code","first_name","last_name","position","hired_on","username","active"}
    if editing: allowed-={"staff_code"}
    if set(data)-allowed-({"revision"} if editing else set()): raise ValueError("Champs inconnus ou non modifiables.")
    if not editing and not {"first_name","last_name","position"} <= set(data): raise ValueError("Champs obligatoires manquants.")
    if editing and (type(data.get("revision")) is not int or data["revision"]<1 or len(data)==1): raise ValueError("Révision invalide ou aucune modification.")
    output={}
    for k,v in data.items():
        if k=="revision": continue
        if k=="staff_code":
            if v == "":
                continue
            if not isinstance(v,str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,49}",v): raise ValueError("Matricule invalide.")
        if k in ("first_name","last_name","position"):
            if not isinstance(v,str) or not (1<=len(v.strip())<=(100 if k=="position" else 120)): raise ValueError("Nom ou fonction invalide.")
            v=v.strip()
        if k=="username":
            if v is not None and (not isinstance(v,str) or len(v)>150 or not v.strip()): raise ValueError("Compte invalide.")
        if k=="hired_on":
            if v is None: pass
            elif not isinstance(v,str): raise ValueError("Date ISO invalide.")
            else:
                try:
                    v=date.fromisoformat(v)
                    if v.isoformat()!=data[k]: raise ValueError()
                except ValueError: raise ValueError("Date ISO invalide.") from None
        if k=="active" and type(v) is not bool: raise ValueError("Statut invalide.")
        output[k]=v
    if not editing and "staff_code" not in output:
        output["staff_code"] = "P-" + uuid4().hex.upper()
    return output


def staff_repr(s, has_photo=None, presentation=None):
    if has_photo is None:
        has_photo = StaffProfile.objects.filter(staff_id=s.pk, photo_data__isnull=False).exists()
    if presentation is None:
        presentation = StaffProfile.objects.filter(staff_id=s.pk).values_list("presentation", flat=True).first() or ""
    return {"id":str(s.id),"staff_code":s.staff_code,"first_name":s.first_name,
        "last_name":s.last_name,"position":s.position,
        "hired_on":s.hired_on.isoformat() if s.hired_on else None,
        "account_id":str(s.account_id) if s.account_id else None,
        "active":s.active,"revision":s.revision,
        "photo_url":f"/api/v1/schools/{s.school_id}/staff/{s.pk}/photo" if has_photo else None,
        "presentation":presentation}


def assignment_repr(s):
    return {"id":str(s.id),"staff":str(s.staff_id),"year":str(s.year_id),
        "classroom":str(s.classroom_id),"duty":s.duty,"active":s.active,"revision":s.revision}


def fail_validation(exc):
    if hasattr(exc,"message_dict"):
        messages=[m for group in exc.message_dict.values() for m in group]
    else: messages=exc.messages
    return JsonResponse({"error":" ".join(messages)[:500]},status=422)


@require_http_methods(["GET","POST"])
@authorized
def staff(request,school_id):
    school,error=scope(request,school_id,"school.staff.read" if request.method=="GET" else "school.staff.manage")
    if error is not None: return error
    if request.method=="GET":
        members = list(StaffRecord.objects.filter(school=school).order_by("last_name","first_name")[:500])
        ids = [s.pk for s in members]
        photo_ids = set(StaffProfile.objects.filter(
            staff_id__in=ids, photo_data__isnull=False,
        ).values_list("staff_id", flat=True))
        presentations = dict(StaffProfile.objects.filter(
            staff_id__in=ids,
        ).values_list("staff_id", "presentation"))
        return JsonResponse({"staff":[staff_repr(
            s, has_photo=s.pk in photo_ids, presentation=presentations.get(s.pk, ""),
        ) for s in members]})
    data,error=parse_body(request)
    if error is not None:return error
    try:
        values=parse_staff(data)
        username=values.pop("username",None)
        account=None
        if username:
            account=get_user_model().objects.filter(username=username.strip(),is_active=True).first()
            if account is None or not SchoolMember.objects.filter(school=school,user=account,active=True).exists():
                raise ValueError("Le compte n'est pas membre actif de cette école.")
        with transaction.atomic():
            record=StaffRecord(school=school,account=account,**values)
            record.full_clean();record.save()
            log_event(school,request,"staff_created",record.id)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    except ValidationError as exc:return fail_validation(exc)
    except IntegrityError:return JsonResponse({"error":"Matricule ou compte déjà utilisé."},status=409)
    return JsonResponse(staff_repr(record),status=201)


@require_http_methods(["GET","PATCH"])
@authorized
def staff_detail(request,school_id,staff_id):
    school,error=scope(request,school_id,"school.staff.read" if request.method=="GET" else "school.staff.manage")
    if error is not None:return error
    if request.method=="GET":
        record=StaffRecord.objects.filter(school=school,pk=staff_id).first()
        return JsonResponse(staff_repr(record)) if record else JsonResponse({"error":"Personnel introuvable."},status=404)
    data,error=parse_body(request)
    if error is not None:return error
    try:values=parse_staff(data,editing=True)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    try:
        with transaction.atomic():
            record=StaffRecord.objects.select_for_update().filter(school=school,pk=staff_id).first()
            if record is None:return JsonResponse({"error":"Personnel introuvable."},status=404)
            if record.revision!=data["revision"]:return JsonResponse({"error":"Conflit de version.","revision":record.revision},status=409)
            if "username" in values:
                identifier=values.pop("username")
                if identifier is None:
                    record.account=None
                else:
                    candidate=get_user_model().objects.filter(username=identifier.strip(),is_active=True).first()
                    if candidate is None or not SchoolMember.objects.filter(
                        school=school,user=candidate,active=True,
                    ).exists():
                        raise ValueError("Ce compte n'est pas membre actif de cette école.")
                    record.account=candidate
            for field,value in values.items():setattr(record,field,value)
            record.full_clean();record.revision+=1;record.save()
            log_event(school,request,"staff_updated",record.pk)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    except ValidationError as exc:return fail_validation(exc)
    except IntegrityError:return JsonResponse({"error":"Ce compte est déjà associé à un personnel."},status=409)
    return JsonResponse(staff_repr(record))


def assignment_fields(data,editing=False):
    allowed={"staff","year","classroom","duty","active"}
    if editing:allowed={"duty","active"}
    if set(data)-allowed-({"revision"} if editing else set()):raise ValueError("Champs inconnus.")
    if not editing and not {"staff","year","classroom"}<=set(data):raise ValueError("Rattachements obligatoires.")
    if editing and (type(data.get("revision")) is not int or data["revision"]<1 or len(data)==1):raise ValueError("Révision invalide.")
    output={}
    for key,value in data.items():
        if key=="revision":continue
        if key in ("staff","year","classroom"):
            try:value=UUID(value)
            except (ValueError,TypeError,AttributeError):raise ValueError("Identifiant invalide.") from None
            output[key+"_id"]=value
        elif key=="duty":
            if not isinstance(value,str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,49}",value):raise ValueError("Fonction d'affectation invalide.")
            output[key]=value
        elif key=="active":
            if type(value) is not bool:raise ValueError("Statut invalide.")
            output[key]=value
    return output


@require_http_methods(["GET","POST"])
@authorized
def assignments(request,school_id):
    school,error=scope(request,school_id,"school.staff.read" if request.method=="GET" else "school.staff.manage")
    if error is not None:return error
    if request.method=="GET":
        return JsonResponse({"assignments":[assignment_repr(a) for a in StaffAssignment.objects.filter(school=school).order_by("duty","pk")[:500]]})
    data,error=parse_body(request)
    if error is not None:return error
    try:
        fields=assignment_fields(data)
        staff_record=StaffRecord.objects.filter(school=school,pk=fields["staff_id"]).first()
        year=AcademicYear.objects.filter(school=school,pk=fields["year_id"]).first()
        classroom=AcademicClass.objects.filter(school=school,pk=fields["classroom_id"]).first()
        if not staff_record or not year or not classroom:raise ValueError("Personnel, année ou classe introuvable dans cette école.")
        if not staff_record.active or not year.active or not classroom.active:raise ValueError("Impossible d'affecter à une ressource archivée.")
        with transaction.atomic():
            a=StaffAssignment(school=school,**fields)
            a.full_clean();a.save()
            log_event(school,request,"staff_assigned",a.pk)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    except ValidationError as exc:return fail_validation(exc)
    except IntegrityError:return JsonResponse({"error":"Affectation déjà enregistrée."},status=409)
    return JsonResponse(assignment_repr(a),status=201)


@require_http_methods(["GET","PATCH"])
@authorized
def assignment_detail(request,school_id,assignment_id):
    school,error=scope(request,school_id,"school.staff.read" if request.method=="GET" else "school.staff.manage")
    if error is not None:return error
    if request.method=="GET":
        obj=StaffAssignment.objects.filter(school=school,pk=assignment_id).first()
        return JsonResponse(assignment_repr(obj)) if obj else JsonResponse({"error":"Affectation introuvable."},status=404)
    data,error=parse_body(request)
    if error is not None:return error
    try:fields=assignment_fields(data,editing=True)
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    try:
        with transaction.atomic():
            obj=StaffAssignment.objects.select_for_update().filter(school=school,pk=assignment_id).first()
            if obj is None:return JsonResponse({"error":"Affectation introuvable."},status=404)
            if obj.revision!=data["revision"]:return JsonResponse({"error":"Conflit de version.","revision":obj.revision},status=409)
            for k,v in fields.items():setattr(obj,k,v)
            obj.full_clean();obj.revision+=1;obj.save()
            log_event(school,request,"assignment_updated",obj.pk)
    except ValidationError as exc:return fail_validation(exc)
    return JsonResponse(assignment_repr(obj))


@require_GET
@authorized
def my_assignments(request,school_id):
    school,error=access(request,school_id)
    if error is not None:return error
    rows=StaffAssignment.objects.filter(school=school,staff__account=request.user,staff__active=True,active=True)
    cycles=scoped_cycle_ids(request.user,school)
    if cycles is not None:
        rows=rows.filter(classroom__level__cycle_id__in=cycles)
    return JsonResponse({"assignments":[assignment_repr(a) for a in rows.order_by("year_id","pk")[:200]]})
