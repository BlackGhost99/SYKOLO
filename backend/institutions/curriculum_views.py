"""Class subjects and configurable teaching programs."""
import re
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .views import access, delete_unused, refuse, parse_body, log_event
from .services import has_permission
from .models import School
from .academic_models import AcademicClass, AcademicYear
from .staff_models import StaffAssignment
from .curriculum_models import Subject, CourseOffering, CourseUnit, CourseInstructor


def access_to(request, school_id, permission):
    school,error=access(request,school_id)
    if error is not None: return None,error
    if not has_permission(request.user,school,permission): return None,refuse()
    return school,None


def object_output(obj):
    d={"id":str(obj.pk),"revision":obj.revision,"active":obj.active}
    if isinstance(obj,Subject):
        d.update(code=obj.code,name=obj.name,description=obj.description)
    elif isinstance(obj,CourseOffering):
        d.update(year=str(obj.year_id),classroom=str(obj.classroom_id),subject=str(obj.subject_id),coefficient=str(obj.coefficient))
    elif isinstance(obj,CourseUnit):
        d.update(course=str(obj.course_id),code=obj.code,title=obj.title,objectives=obj.objectives,order=obj.order)
    elif isinstance(obj,CourseInstructor):
        d.update(course=str(obj.course_id),staff_assignment=str(obj.staff_assignment_id))
    return d


def parsed(data,fields,required=(),editing=False):
    if set(data)-set(fields)-({"revision"} if editing else set()): raise ValueError("Champs non modifiables.")
    if not editing and not set(required) <= set(data): raise ValueError("Champs obligatoires manquants.")
    if editing and (type(data.get("revision")) is not int or data["revision"]<1 or len(data)<=1): raise ValueError("Révision invalide.")
    out={}
    for key,value in data.items():
        if key=="revision":continue
        if key in ("year","classroom","subject","staff_assignment"):
            try: out[key+"_id"]=UUID(value)
            except (ValueError,TypeError,AttributeError): raise ValueError("Identifiant invalide.") from None
        elif key=="coefficient":
            if type(value) not in (int,float,str):raise ValueError("Coefficient invalide.")
            try:
                n=Decimal(str(value))
                if not n.is_finite() or not Decimal("0")<n<=Decimal("1000"): raise ValueError()
            except (InvalidOperation,ValueError):raise ValueError("Coefficient invalide.") from None
            out[key]=n
        elif key in ("code",):
            if not isinstance(value,str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,49}",value):raise ValueError("Code invalide.")
            out[key]=value
        elif key in ("name","title"):
            if not isinstance(value,str) or not 1<=len(value.strip())<=(180 if key=="title" else 120):raise ValueError("Intitulé invalide.")
            out[key]=value.strip()
        elif key in ("description","objectives"):
            if not isinstance(value,str) or len(value)>(500 if key=="description" else 2000): raise ValueError("Description trop longue.")
            out[key]=value.strip()
        elif key=="order":
            if type(value) is not int or not 0<=value<=1000:raise ValueError("Ordre invalide.")
            out[key]=value
        elif key=="active":
            if type(value) is not bool:raise ValueError("Statut invalide.")
            out[key]=value
    return out


def validation(exc):
    if hasattr(exc,"message_dict"):
        messages=[m for group in exc.message_dict.values() for m in group]
    else: messages=exc.messages
    return JsonResponse({"error":" ".join(messages)[:500]},status=422)


def mutate(request, school, model, data, allowed, required=(), obj=None):
    updating=obj is not None
    try: values=parsed(data,allowed,required,editing=updating)
    except ValueError as exc: return JsonResponse({"error":str(exc)},status=422)
    try:
        with transaction.atomic():
            if updating:
                obj=model.objects.select_for_update().filter(school=school,pk=obj.pk).first()
                if obj is None: return JsonResponse({"error":"Élément introuvable."},status=404)
                if obj.revision!=data["revision"]: return JsonResponse({"error":"Conflit de version.","revision":obj.revision},status=409)
                for k,v in values.items(): setattr(obj,k,v)
                obj.full_clean();obj.revision+=1;obj.save()
            else:
                obj=model(school=school,**values)
                obj.full_clean();obj.save()
            log_event(school,request,"curriculum_updated" if updating else "curriculum_created",f"{model.__name__}:{obj.pk}")
    except ValidationError as exc: return validation(exc)
    except IntegrityError: return JsonResponse({"error":"Code ou rattachement déjà présent."},status=409)
    return JsonResponse(object_output(obj),status=200 if updating else 201)


@require_http_methods(["GET","POST"])
@authorized
def subjects(request,school_id):
    school,error=access_to(request,school_id,"school.curriculum.read" if request.method=="GET" else "school.curriculum.manage")
    if error is not None:return error
    if request.method=="GET":
        return JsonResponse({"subjects":[object_output(s) for s in Subject.objects.filter(school=school).order_by("name")[:500]],
                             "can_manage":has_permission(request.user,school,"school.curriculum.manage")})
    body,error=parse_body(request)
    if error is not None:return error
    return mutate(request,school,Subject,body,("code","name","description","active"),("code","name"))


@require_http_methods(["GET","PATCH","DELETE"])
@authorized
def subject_detail(request,school_id,subject_id):
    school,error=access_to(request,school_id,"school.curriculum.read" if request.method=="GET" else "school.curriculum.manage")
    if error is not None:return error
    obj=Subject.objects.filter(school=school,pk=subject_id).first()
    if obj is None:return JsonResponse({"error":"Matière introuvable."},status=404)
    if request.method=="GET":return JsonResponse(object_output(obj))
    body,error=parse_body(request)
    if error is not None:return error
    if request.method=="DELETE":return remove_curriculum(request,school,Subject,obj.pk,body)
    return mutate(request,school,Subject,body,("name","description","active"),obj=obj)


@require_http_methods(["GET","POST"])
@authorized
def courses(request,school_id):
    school,error=access_to(request,school_id,"school.curriculum.read" if request.method=="GET" else "school.curriculum.manage")
    if error is not None:return error
    if request.method=="GET":
        return JsonResponse({"courses":[object_output(s) for s in CourseOffering.objects.filter(school=school).order_by("subject__name","pk")[:500]]})
    body,error=parse_body(request)
    if error is not None:return error
    return mutate(request,school,CourseOffering,body,
        ("year","classroom","subject","coefficient","active"),("year","classroom","subject"))


@require_http_methods(["GET"])
@authorized
def my_courses(request, school_id):
    """Teaching courses actually assigned to the current staff account.

    This is NOT school-wide assessment read access. Every assessment and grade
    endpoint still verifies CourseInstructor assignment independently.
    """
    school, error = access_to(request, school_id, "school.curriculum.read")
    if error is not None:
        return error
    rows = CourseOffering.objects.filter(
        school=school, active=True, year__active=True,
        classroom__active=True, subject__active=True,
        instructors__active=True,
        instructors__staff_assignment__active=True,
        instructors__staff_assignment__staff__active=True,
        instructors__staff_assignment__staff__account=request.user,
    ).distinct().order_by("year_id", "classroom_id", "subject__name")
    return JsonResponse({"courses": [object_output(row) for row in rows[:300]]})


@require_http_methods(["GET","PATCH","DELETE"])
@authorized
def course_detail(request,school_id,course_id):
    school,error=access_to(request,school_id,"school.curriculum.read" if request.method=="GET" else "school.curriculum.manage")
    if error is not None:return error
    obj=CourseOffering.objects.filter(school=school,pk=course_id).first()
    if obj is None:return JsonResponse({"error":"Cours introuvable."},status=404)
    if request.method=="GET":return JsonResponse(object_output(obj))
    body,error=parse_body(request)
    if error is not None:return error
    if request.method=="DELETE":return remove_curriculum(request,school,CourseOffering,obj.pk,body)
    return mutate(request,school,CourseOffering,body,("coefficient","active"),obj=obj)


def remove_curriculum(request, school, model, key, body):
    try:
        with transaction.atomic():
            obj = model.objects.select_for_update().filter(school=school, pk=key).first()
            if obj is None:
                return JsonResponse({"error": "Élément introuvable."}, status=404)
            return delete_unused(request, school, obj, body, "curriculum_deleted")
    except IntegrityError:
        return JsonResponse({"error": "Cet élément est utilisé. Archivez-le pour conserver son historique."}, status=409)


@require_http_methods(["POST"])
@authorized
def generate_courses(request, school_id):
    school, error = access_to(request, school_id, "school.curriculum.manage")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    try:
        if set(data) != {"classroom", "names"} or not isinstance(data["names"], list) or not 1 <= len(data["names"]) <= 30:
            raise ValueError("Indiquez une classe et 1 à 30 matières.")
        classroom_id = parsed({"classroom": data["classroom"]}, ("classroom",))["classroom_id"]
        names = {}
        for value in data["names"]:
            name = parsed({"name": value}, ("name",))["name"]
            names.setdefault(name.casefold(), name)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            School.objects.select_for_update(no_key=True).get(pk=school.pk)
            classroom = AcademicClass.objects.select_for_update().filter(school=school, pk=classroom_id).first()
            if classroom is None:
                return JsonResponse({"error": "Classe introuvable."}, status=404)
            if not classroom.active or not classroom.year.active:
                return JsonResponse({"error": "Choisissez une classe et une année actives."}, status=422)
            catalog = list(Subject.objects.filter(school=school).order_by("active", "pk"))
            by_name = {subject.name.casefold(): subject for subject in catalog}
            taken_codes = {subject.code for subject in catalog}
            assigned = {row.subject_id: row for row in CourseOffering.objects.filter(school=school, classroom=classroom)}
            created = []
            skipped = []
            archived = []
            for key, name in names.items():
                subject = by_name.get(key)
                if subject is None:
                    prefix = (slugify(name) or "matiere")[:44]
                    code = prefix
                    suffix = 2
                    while code in taken_codes:
                        code = f"{prefix}-{suffix}"
                        suffix += 1
                    subject = Subject.objects.create(school=school, code=code, name=name)
                    taken_codes.add(code)
                    log_event(school, request, "curriculum_created", f"Subject:{subject.pk}")
                offering = assigned.get(subject.pk)
                if not subject.active or (offering is not None and not offering.active):
                    archived.append(name)
                elif offering is not None:
                    skipped.append(name)
                else:
                    offering = CourseOffering.objects.create(
                        school=school, classroom=classroom, year_id=classroom.year_id, subject=subject,
                    )
                    created.append(name)
                    log_event(school, request, "curriculum_created", f"CourseOffering:{offering.pk}")
    except IntegrityError:
        return JsonResponse({"error": "Une modification simultanée a empêché la génération. Réessayez."}, status=409)
    return JsonResponse({"created": created, "existing": skipped, "archived": archived}, status=201 if created else 200)


def can_manage_course(request,school,course):
    if has_permission(request.user,school,"school.curriculum.manage"):return True
    return CourseInstructor.objects.filter(
        school=school,course=course,active=True,staff_assignment__active=True,
        staff_assignment__staff__active=True,staff_assignment__staff__account=request.user
    ).exists()


@require_http_methods(["GET","POST"])
@authorized
def units(request,school_id,course_id):
    school,error=access_to(request,school_id,"school.curriculum.read")
    if error is not None:return error
    course=CourseOffering.objects.filter(school=school,pk=course_id).first()
    if course is None:return JsonResponse({"error":"Cours introuvable."},status=404)
    if request.method=="GET":
        return JsonResponse({"units":[object_output(x) for x in course.units.order_by("order","pk")[:500]],
                             "can_manage":can_manage_course(request,school,course)})
    if not can_manage_course(request,school,course):return refuse()
    body,error=parse_body(request)
    if error is not None:return error
    try: fields=parsed(body,("code","title","objectives","order","active"),("code","title"))
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    return create_unit(request,school,course,fields)


def create_unit(request,school,course,fields):
    try:
        with transaction.atomic():
            u=CourseUnit(school=school,course=course,**fields)
            u.full_clean();u.save()
            log_event(school,request,"course_unit_created",u.pk)
    except ValidationError as exc:return validation(exc)
    except IntegrityError:return JsonResponse({"error":"Unité déjà présente."},status=409)
    return JsonResponse(object_output(u),status=201)


@require_http_methods(["GET","PATCH"])
@authorized
def unit_detail(request,school_id,course_id,unit_id):
    school,error=access_to(request,school_id,"school.curriculum.read")
    if error is not None:return error
    course=CourseOffering.objects.filter(school=school,pk=course_id).first()
    if course is None:return JsonResponse({"error":"Cours introuvable."},status=404)
    unit=CourseUnit.objects.filter(school=school,course=course,pk=unit_id).first()
    if unit is None:return JsonResponse({"error":"Unité introuvable."},status=404)
    if request.method=="GET":return JsonResponse(object_output(unit))
    if not can_manage_course(request,school,course):return refuse()
    body,error=parse_body(request)
    if error is not None:return error
    return mutate(request,school,CourseUnit,body,("title","objectives","order","active"),obj=unit)


@require_http_methods(["GET","POST"])
@authorized
def instructors(request,school_id,course_id):
    school,error=access_to(request,school_id,"school.curriculum.read" if request.method=="GET" else "school.curriculum.manage")
    if error is not None:return error
    course=CourseOffering.objects.filter(school=school,pk=course_id).first()
    if course is None:return JsonResponse({"error":"Cours introuvable."},status=404)
    if request.method=="GET":
        return JsonResponse({"instructors":[object_output(x) for x in course.instructors.order_by("pk")[:100]]})
    body,error=parse_body(request)
    if error is not None:return error
    try:fields=parsed(body,("staff_assignment","active"),("staff_assignment",))
    except ValueError as exc:return JsonResponse({"error":str(exc)},status=422)
    assignment=StaffAssignment.objects.filter(school=school,pk=fields["staff_assignment_id"]).first()
    if not assignment:return JsonResponse({"error":"Affectation introuvable."},status=422)
    try:
        with transaction.atomic():
            obj=CourseInstructor(school=school,course=course,**fields)
            obj.full_clean();obj.save()
            log_event(school,request,"course_instructor_added",obj.pk)
    except ValidationError as exc:return validation(exc)
    except IntegrityError:return JsonResponse({"error":"Enseignant déjà associé."},status=409)
    return JsonResponse(object_output(obj),status=201)


@require_http_methods(["PATCH"])
@authorized
def instructor_detail(request,school_id,course_id,instructor_id):
    school,error=access_to(request,school_id,"school.curriculum.manage")
    if error is not None:return error
    obj=CourseInstructor.objects.filter(school=school,course_id=course_id,pk=instructor_id).first()
    if obj is None:return JsonResponse({"error":"Enseignant introuvable."},status=404)
    body,error=parse_body(request)
    if error is not None:return error
    return mutate(request,school,CourseInstructor,body,("active",),obj=obj)
