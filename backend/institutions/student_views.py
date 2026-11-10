"""Institutionally scoped admissions and learner records; no public learner directory."""
import re
from datetime import date
from uuid import UUID
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods
from accounts.views import authorized
from .views import access, refuse, parse_body, log_event
from .services import has_permission, quota_reached
from .cycle_scope import scoped_cycle_ids
from .academic_models import AcademicYear, AcademicClass
from .student_models import Student, StudentGuardian, Enrollment, EnrollmentEvent
from .admission_finance import direct_enrollment_blocker


def check(request, school_id, permission):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, permission):
        return None, refuse()
    return school, None


def visible_students(user, school):
    result = Student.objects.filter(school=school)
    cycles = scoped_cycle_ids(user, school)
    if cycles is not None:
        result = result.filter(enrollments__active=True, enrollments__classroom__level__cycle_id__in=cycles).distinct()
    return result


def visible_enrollments(user, school):
    result = Enrollment.objects.filter(school=school)
    cycles = scoped_cycle_ids(user, school)
    if cycles is not None:
        result = result.filter(classroom__level__cycle_id__in=cycles)
    return result


TEXT_LIMITS = {"place_of_birth": 120, "nationality": 80, "address": 255, "previous_school": 180, "profession": 120}
STUDENT_INFO = ("gender", "place_of_birth", "nationality", "address", "previous_school")
GUARDIAN_INFO = ("profession", "address")


def parse_fields(data, allowed, required=(), *, revision=False):
    if set(data) - set(allowed) - ({"revision"} if revision else set()):
        raise ValueError("Champs inconnus ou non modifiables.")
    if not revision and not set(required).issubset(data):
        raise ValueError("Champs obligatoires manquants.")
    if revision and (type(data.get("revision")) is not int or data["revision"] < 1):
        raise ValueError("Révision requise.")
    if revision and len(data) == 1:
        raise ValueError("Aucune modification.")
    clean = {}
    for key, value in data.items():
        if key == "revision":
            continue
        if key == "student_code":
            if not isinstance(value, str) or not 1 <= len(value) <= 50 or not value.isprintable():
                raise ValueError("Matricule local invalide (50 caractères imprimables au maximum).")
        elif key == "status":
            if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}", value):
                raise ValueError("Statut invalide.")
        elif key in ("first_name", "last_name", "full_name"):
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= (180 if key == "full_name" else 120):
                raise ValueError("Nom invalide.")
            value = value.strip()
        elif key in TEXT_LIMITS:
            if not isinstance(value, str) or len(value) > TEXT_LIMITS[key] or any(ord(c) < 32 for c in value):
                raise ValueError("Texte invalide ou trop long.")
            value = value.strip()
        elif key == "gender":
            if value not in ("", "F", "M"):
                raise ValueError("Sexe invalide.")
        elif key == "relationship":
            if not isinstance(value, str) or len(value) > 80:
                raise ValueError("Lien de parenté invalide.")
        elif key == "phone":
            if not isinstance(value, str) or len(value) > 45 or any(ord(c) < 32 for c in value):
                raise ValueError("Numéro invalide.")
        elif key == "email":
            if not isinstance(value, str) or len(value) > 254:
                raise ValueError("Adresse email invalide.")
        elif key in ("date_of_birth", "admission_date", "enrolled_on"):
            if value is None and key != "enrolled_on":
                pass
            elif not isinstance(value, str):
                raise ValueError("Date invalide.")
            else:
                try:
                    value = date.fromisoformat(value)
                    if value.isoformat() != data[key]:
                        raise ValueError()
                except ValueError:
                    raise ValueError("Date ISO invalide.") from None
        elif key in ("active", "is_primary"):
            if type(value) is not bool:
                raise ValueError("Booléen attendu.")
        elif key in ("student", "year", "classroom"):
            try:
                value = UUID(value)
            except (TypeError, ValueError, AttributeError):
                raise ValueError("Identifiant incorrect.") from None
        clean[key] = value
    return clean


def describe(obj):
    result = {"id": str(obj.pk), "revision": obj.revision}
    if isinstance(obj, Student):
        fields = ("student_code", "matricule_yem", "first_name", "last_name", "date_of_birth", "admission_date", *STUDENT_INFO, "extra_fields", "documents", "active")
    elif isinstance(obj, StudentGuardian):
        fields = ("full_name", "relationship", "phone", "email", *GUARDIAN_INFO, "is_primary", "active")
    else:
        fields = ("student_id", "year_id", "classroom_id", "enrolled_on", "status", "active")
    for field in fields:
        val = getattr(obj, field)
        result[field[:-3] if field.endswith("_id") else field] = val.isoformat() if isinstance(val,date) else str(val) if isinstance(val,UUID) else val
    return result


def validation_response(exc):
    if hasattr(exc, "message_dict"):
        messages = [msg for group in exc.message_dict.values() for msg in group]
    else:
        messages = exc.messages
    return JsonResponse({"error": " ".join(messages)[:500]}, status=422)


@require_http_methods(["GET", "POST"])
@authorized
def students(request, school_id):
    school, error = check(request, school_id, "school.students.read" if request.method == "GET" else "school.students.manage")
    if error is not None: return error
    if request.method == "GET":
        rows = visible_students(request.user, school)
        matricule = request.GET.get("matricule")
        if matricule is not None:
            if not re.fullmatch(r"YEM-[0-9A-F]{32}", matricule.strip().upper()):
                return JsonResponse({"error": "Matricule YEM invalide."}, status=422)
            rows = rows.filter(identity_id=UUID(hex=matricule.strip()[4:]))
        return JsonResponse({"students": [describe(s) for s in rows.order_by("last_name","first_name")[:500]]})
    data, error = parse_body(request)
    if error is not None: return error
    try:
        data.pop("student_code", None)  # Compatibility with clients that still send the old field.
        values = parse_fields(data, ("first_name", "last_name", "date_of_birth", "admission_date", *STUDENT_INFO, "active"), ("first_name", "last_name"))
        with transaction.atomic():
            from .models import School
            School.objects.select_for_update().get(pk=school.pk)
            if values.get("active", True) and quota_reached(school, "students"):
                return JsonResponse({"error": "Plafond d'élèves atteint pour cet établissement."}, status=409)
            student = Student(school=school, **values)
            student.full_clean()
            student.save()
            log_event(school, request, "student_created", student.pk)
    except ValueError as exc: return JsonResponse({"error": str(exc)}, status=422)
    except ValidationError as exc: return validation_response(exc)
    except IntegrityError: return JsonResponse({"error": "Code élève déjà utilisé."}, status=409)
    return JsonResponse(describe(student), status=201)


@require_http_methods(["GET", "PATCH"])
@authorized
def student_detail(request, school_id, student_id):
    school, error = check(request, school_id, "school.students.read" if request.method == "GET" else "school.students.manage")
    if error is not None: return error
    if request.method == "GET":
        student = visible_students(request.user,school).filter(id=student_id).first()
        return JsonResponse(describe(student)) if student else JsonResponse({"error": "Élève introuvable."}, status=404)
    data,error = parse_body(request)
    if error is not None: return error
    if not isinstance(data, dict): return JsonResponse({"error": "Objet JSON attendu."}, status=422)
    answers = {k: data.pop(k) for k in ("extra_fields", "documents") if k in data}
    try:
        if answers and set(data) == {"revision"}:
            if type(data["revision"]) is not int or data["revision"] < 1: raise ValueError("Révision requise.")
            fields = {}
        else:
            fields = parse_fields(data, ("first_name", "last_name", "date_of_birth", "admission_date", *STUDENT_INFO, "active"), revision=True)
        if answers:
            from .enrollment_form import load_config, clean_answers
            extra, docs = clean_answers(load_config(school)[0], answers.get("extra_fields"), answers.get("documents"), partial=True)
            if "extra_fields" in answers: fields["extra_fields"] = extra
            if "documents" in answers: fields["documents"] = docs
    except ValueError as exc: return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            obj = Student.objects.select_for_update().filter(school=school, pk=student_id).first()
            if obj is None: return JsonResponse({"error": "Élève introuvable."}, status=404)
            if obj.revision != data["revision"]: return JsonResponse({"error": "Conflit de version.", "revision": obj.revision}, status=409)
            if fields.get("active") is True and not obj.active:
                from .models import School
                School.objects.select_for_update().get(pk=school.pk)
                if quota_reached(school, "students"):
                    return JsonResponse({"error": "Plafond d'élèves atteint pour cet établissement."}, status=409)
            for field,value in fields.items(): setattr(obj, field, value)
            obj.full_clean()
            obj.revision += 1
            obj.save()
            log_event(school, request, "student_updated", obj.pk)
    except ValidationError as exc: return validation_response(exc)
    return JsonResponse(describe(obj))


@require_http_methods(["GET","POST"])
@authorized
def guardians(request, school_id, student_id):
    school, error = check(request, school_id, "school.students.read" if request.method == "GET" else "school.students.manage")
    if error is not None: return error
    student = visible_students(request.user,school).filter(pk=student_id).first()
    if student is None: return JsonResponse({"error": "Élève introuvable."}, status=404)
    if request.method == "GET":
        return JsonResponse({"guardians": [describe(g) for g in student.guardians.order_by("full_name")[:100]]})
    data,error = parse_body(request)
    if error is not None: return error
    try:
        fields=parse_fields(data,("full_name","relationship","phone","email",*GUARDIAN_INFO,"is_primary","active"),("full_name",))
        with transaction.atomic():
            g=StudentGuardian(school=school,student=student,**fields)
            g.full_clean();g.save();log_event(school,request,"guardian_added",student.pk)
    except ValueError as exc: return JsonResponse({"error":str(exc)},status=422)
    except ValidationError as exc: return validation_response(exc)
    return JsonResponse(describe(g),status=201)


@require_GET
@authorized
def guardians_by_class(request, school_id):
    school, error = check(request, school_id, "school.parents.manage")
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.students.read"):
        return refuse()
    try:
        classroom_id = UUID(request.GET.get("classroom", ""))
    except ValueError:
        return JsonResponse({"error": "Classe invalide."}, status=422)
    if not AcademicClass.objects.filter(school=school, pk=classroom_id).exists():
        return JsonResponse({"error": "Classe introuvable."}, status=404)
    roster = visible_enrollments(request.user, school).filter(
        classroom_id=classroom_id, active=True, student__active=True,
    ).select_related("student").prefetch_related("student__guardians").order_by(
        "student__last_name", "student__first_name", "pk",
    )
    return JsonResponse({"families": [
        {
            "student_id": str(row.student_id),
            "student_name": f"{row.student.first_name} {row.student.last_name}",
            "guardians": [
                {"id": str(guardian.pk), "name": guardian.full_name, "relationship": guardian.relationship,
                 "phone": guardian.phone, "email": guardian.email}
                for guardian in row.student.guardians.all()
                if guardian.active and guardian.school_id == school.pk
            ],
        }
        for row in roster
    ]})


@require_http_methods(["PATCH"])
@authorized
def guardian_detail(request, school_id, student_id, guardian_id):
    school,error=check(request,school_id,"school.students.manage")
    if error is not None: return error
    data,error=parse_body(request)
    if error is not None: return error
    try: fields=parse_fields(data,("full_name","relationship","phone","email",*GUARDIAN_INFO,"is_primary","active"),revision=True)
    except ValueError as exc: return JsonResponse({"error":str(exc)},status=422)
    try:
        with transaction.atomic():
            g=StudentGuardian.objects.select_for_update().filter(school=school,student_id=student_id,pk=guardian_id).first()
            if g is None: return JsonResponse({"error":"Responsable introuvable."},status=404)
            if g.revision != data["revision"]: return JsonResponse({"error":"Conflit de version.","revision":g.revision},status=409)
            for k,v in fields.items(): setattr(g,k,v)
            g.full_clean();g.revision+=1;g.save()
            log_event(school,request,"guardian_updated",student_id)
    except ValidationError as exc: return validation_response(exc)
    return JsonResponse(describe(g))


def load_relations(school, values):
    student=Student.objects.filter(school=school,pk=values["student"]).first()
    year=AcademicYear.objects.filter(school=school,pk=values["year"]).first()
    classroom=AcademicClass.objects.filter(school=school,pk=values["classroom"]).first()
    if not student or not year or not classroom:
        raise ValueError("Élève, année ou classe introuvable dans cet établissement.")
    return student,year,classroom


def validate_enrollment_slot(classroom, student, year, *, active=True, enrollment=None):
    if classroom.year_id != year.pk or classroom.school_id != student.school_id:
        raise ValueError("Classe et inscription incohérentes.")
    if active and (not classroom.active or not year.active or year.status == AcademicYear.STATUS_CLOSED
                   or not student.active or not classroom.level.active or not classroom.level.cycle.active
                   or (classroom.track_id and not classroom.track.active)):
        raise ValueError("Impossible d'inscrire dans une classe, une année ou un dossier archivé.")
    if active and classroom.capacity is not None:
        active_rows=Enrollment.objects.filter(classroom=classroom,active=True)
        if enrollment: active_rows=active_rows.exclude(pk=enrollment.pk)
        if active_rows.count() >= classroom.capacity:
            raise ValueError("Capacité de classe atteinte.")


@require_http_methods(["GET","POST"])
@authorized
def enrollments(request,school_id):
    school,error=check(request,school_id,"school.students.read" if request.method=="GET" else "school.students.manage")
    if error is not None: return error
    if request.method=="GET":
        student_id=request.GET.get("student")
        qs=visible_enrollments(request.user,school).order_by("-enrolled_on","pk")
        if student_id:
            try: qs=qs.filter(student_id=UUID(student_id))
            except (ValueError,TypeError): return JsonResponse({"error":"Identifiant invalide."},status=422)
        return JsonResponse({"enrollments":[describe(en) for en in qs[:500]]})
    data,error=parse_body(request)
    if error is not None: return error
    try:
        fields=parse_fields(data,("student","year","classroom","enrolled_on","status","active"),("student","year","classroom","enrolled_on"))
        with transaction.atomic():
            student,year,classroom=load_relations(school,fields)
            # Lock class before counting places. Works with PostgreSQL concurrency.
            classroom=AcademicClass.objects.select_for_update().get(pk=classroom.pk,school=school)
            blocker = direct_enrollment_blocker(school, classroom)
            if blocker:
                return JsonResponse({"error": blocker}, status=409)
            validate_enrollment_slot(classroom,student,year,active=fields.get("active",True))
            values={k+"_id" if k in ("student","year","classroom") else k:v for k,v in fields.items()}
            record=Enrollment(school=school,**values)
            record.full_clean();record.save()
            EnrollmentEvent.objects.create(enrollment=record,school=school,actor=request.user,
                previous_class_id=None,new_class_id=record.classroom_id,new_status=record.status)
            log_event(school,request,"enrollment_created",record.pk)
    except ValueError as exc: return JsonResponse({"error":str(exc)},status=422)
    except ValidationError as exc: return validation_response(exc)
    except IntegrityError: return JsonResponse({"error":"Élève déjà inscrit pour cette année."},status=409)
    return JsonResponse(describe(record),status=201)


@require_http_methods(["GET","PATCH"])
@authorized
def enrollment_detail(request,school_id,enrollment_id):
    school,error=check(request,school_id,"school.students.read" if request.method=="GET" else "school.students.manage")
    if error is not None: return error
    if request.method=="GET":
        record=visible_enrollments(request.user,school).filter(pk=enrollment_id).first()
        return JsonResponse(describe(record)) if record else JsonResponse({"error":"Inscription introuvable."},status=404)
    data,error=parse_body(request)
    if error is not None: return error
    try: fields=parse_fields(data,("classroom","status","active"),revision=True)
    except ValueError as exc: return JsonResponse({"error":str(exc)},status=422)
    try:
        with transaction.atomic():
            rec=Enrollment.objects.select_for_update().filter(school=school,pk=enrollment_id).first()
            if rec is None: return JsonResponse({"error":"Inscription introuvable."},status=404)
            if rec.revision!=data["revision"]: return JsonResponse({"error":"Conflit de version.","revision":rec.revision},status=409)
            new_class=AcademicClass.objects.filter(school=school,pk=fields.get("classroom",rec.classroom_id)).first()
            if not new_class: raise ValueError("Classe introuvable.")
            new_class=AcademicClass.objects.select_for_update().get(pk=new_class.pk)
            validate_enrollment_slot(new_class,rec.student,rec.year,active=fields.get("active",rec.active),enrollment=rec)
            previous_class=rec.classroom_id
            previous_status=rec.status
            for key,val in fields.items(): setattr(rec,"classroom_id" if key=="classroom" else key,val)
            rec.full_clean();rec.revision+=1;rec.save()
            EnrollmentEvent.objects.create(enrollment=rec,school=school,actor=request.user,
                previous_class_id=previous_class,new_class_id=rec.classroom_id,
                previous_status=previous_status,new_status=rec.status)
            log_event(school,request,"enrollment_updated",rec.pk)
    except ValueError as exc: return JsonResponse({"error":str(exc)},status=422)
    except ValidationError as exc: return validation_response(exc)
    return JsonResponse(describe(rec))


@require_http_methods(["GET"])
@authorized
def enrollment_history(request,school_id,enrollment_id):
    school,error=check(request,school_id,"school.students.read")
    if error is not None: return error
    if not Enrollment.objects.filter(school=school,pk=enrollment_id).exists():
        return JsonResponse({"error":"Inscription introuvable."},status=404)
    rows=EnrollmentEvent.objects.filter(school=school,enrollment_id=enrollment_id).order_by("-at")[:100]
    return JsonResponse({"history":[{
        "at":r.at.isoformat(),"previous_class":str(r.previous_class_id) if r.previous_class_id else None,
        "new_class":str(r.new_class_id),"previous_status":r.previous_status,"new_status":r.new_status,
    } for r in rows]})
