"""Parcours simplifiés du secrétariat : fiche de renseignement complète, inscriptions
par classe, création rapide des classes et facturation d'une classe.

Ces vues réutilisent les règles des modules 04, 05 et 11 (isolation par école,
capacité verrouillée, frais figés au barème, audit) et ne font que regrouper en
une seule transaction ce qui demandait auparavant plusieurs écrans.
"""
import re
from collections import Counter
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST
from accounts.views import authorized

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .finance_models import FeeSchedule, FeeCharge, FeePayment
from .overview_views import gate, current_year, enrollment_balances, finance_status, money, ZERO
from .services import has_permission
from .student_models import Student, StudentGuardian, Enrollment, EnrollmentEvent
from .student_views import (
    parse_fields, describe, validate_enrollment_slot, validation_response, STUDENT_INFO, GUARDIAN_INFO,
)
from .views import parse_body, log_event
from .enrollment_form import load_config, clean_answers, check_base, missing_documents

STUDENT_FIELDS = ("student_code", "first_name", "last_name", "date_of_birth", "admission_date", *STUDENT_INFO)
GUARDIAN_FIELDS = ("full_name", "relationship", "phone", "email", *GUARDIAN_INFO, "is_primary")


class Refused(Exception):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def as_uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise Refused("Identifiant incorrect.") from None


def next_student_code(school):
    """Matricule lisible et unique : ELE26-0001, ELE26-0002…"""
    prefix = f"ELE{timezone.localdate():%y}-"
    taken = set(Student.objects.filter(school=school, student_code__startswith=prefix).values_list("student_code", flat=True))
    n = len(taken) + 1
    while f"{prefix}{n:04d}" in taken:
        n += 1
    return f"{prefix}{n:04d}"


def unique_code(base, taken, limit=40):
    base = (slugify(base) or "x")[:limit - 4].strip("-_") or "x"
    code, n = base, 2
    while code in taken:
        code = f"{base}-{n}"
        n += 1
    return code


def apply_fees(school, enrollment, user):
    """Affecte à une inscription les barèmes actifs de son année (école entière ou sa classe)."""
    schedules = FeeSchedule.objects.filter(school=school, year_id=enrollment.year_id, active=True).filter(
        Q(classroom__isnull=True) | Q(classroom_id=enrollment.classroom_id))
    existing = set(FeeCharge.objects.filter(school=school, enrollment=enrollment).values_list("schedule_id", flat=True))
    created = 0
    for s in schedules:
        if s.pk in existing:
            continue
        row = FeeCharge(school=school, enrollment=enrollment, schedule=s, label=s.label, amount=s.amount,
                        currency=s.currency, due_date=s.due_date, created_by=user)
        row.full_clean()
        row.save()
        created += 1
    return created


def enroll(school, request, student, classroom, enrolled_on=None):
    classroom = AcademicClass.objects.select_for_update().get(pk=classroom.pk, school=school)
    year = classroom.year
    if enrolled_on is None:
        today = timezone.localdate()
        enrolled_on = today if year.start_date <= today <= year.end_date else year.start_date
    try:
        validate_enrollment_slot(classroom, student, year)
    except ValueError as exc:
        raise Refused(str(exc)) from None
    if Enrollment.objects.filter(school=school, student=student, year=year).exists():
        raise Refused(f"{student.last_name} {student.first_name} est déjà inscrit(e) pour {year.name}.", 409)
    record = Enrollment(school=school, student=student, year=year, classroom=classroom, enrolled_on=enrolled_on, status="inscrit")
    record.full_clean()
    record.save()
    EnrollmentEvent.objects.create(enrollment=record, school=school, actor=request.user, previous_class_id=None,
                                   new_class_id=record.classroom_id, new_status=record.status)
    log_event(school, request, "enrollment_created", record.pk)
    return record


def respond(fn):
    """Traduit les erreurs métier en réponses JSON homogènes."""
    try:
        return fn()
    except Refused as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except ValidationError as exc:
        return validation_response(exc)
    except IntegrityError:
        return JsonResponse({"error": "Enregistrement en double : vérifiez le matricule ou l'inscription."}, status=409)


@require_POST
@authorized
def register_student(request, school_id):
    """Fiche de renseignement complète : élève + responsables + inscription + frais, en une transaction."""
    school, error = gate(request, school_id, "school.students.manage")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error

    def run():
        if not isinstance(data, dict) or set(data) - {"student", "guardians", "enrollment", "apply_fees"}:
            raise Refused("Champs inconnus.")
        info = data.get("student")
        if not isinstance(info, dict):
            raise Refused("Identité de l'élève requise.")
        info = {k: v for k, v in info.items() if not (k in ("student_code", "date_of_birth", "admission_date") and v in ("", None))}
        guardians = data.get("guardians") or []
        if not isinstance(guardians, list) or len(guardians) > 4 or not all(isinstance(g, dict) for g in guardians):
            raise Refused("Responsables invalides (4 au maximum).")
        wanted = data.get("enrollment")
        if wanted is not None and not isinstance(wanted, dict):
            raise Refused("Inscription invalide.")
        fees_wanted = data.get("apply_fees", True)
        if type(fees_wanted) is not bool:
            raise Refused("Option de facturation invalide.")
        config, _ = load_config(school)
        extra, documents = clean_answers(config, info.pop("extra_fields", None), info.pop("documents", None))
        first_guardian = next((g for g in guardians if str(g.get("full_name") or "").strip()), None)
        if first_guardian is None:
            raise Refused("Le responsable légal principal est obligatoire.")
        check_base(config, info, first_guardian)
        if not config["fields"].get("second_guardian", {}).get("visible", True):
            guardians = [first_guardian]
        with transaction.atomic():
            if not info.get("student_code"):
                info["student_code"] = next_student_code(school)
            values = parse_fields(info, STUDENT_FIELDS, ("student_code", "first_name", "last_name"))
            if Student.objects.filter(school=school, student_code=values["student_code"]).exists():
                raise Refused("Ce matricule est déjà utilisé.", 409)
            student = Student(school=school, extra_fields=extra, documents=documents, **values)
            student.full_clean()
            student.save()
            log_event(school, request, "student_created", student.pk)
            saved_guardians = []
            cleaned = [parse_fields({k: v for k, v in g.items() if v is not None}, GUARDIAN_FIELDS, ("full_name",))
                       for g in guardians if str(g.get("full_name") or "").strip()]
            if cleaned and not any(g.get("is_primary") for g in cleaned):
                cleaned[0]["is_primary"] = True
            for g in cleaned:
                row = StudentGuardian(school=school, student=student, **g)
                row.full_clean()
                row.save()
                saved_guardians.append(row)
            if saved_guardians:
                log_event(school, request, "guardian_added", student.pk)
            enrollment, charges, fees_skipped = None, 0, False
            if wanted and wanted.get("classroom"):
                if not has_permission(request.user, school, "school.students.manage"):
                    raise Refused("Inscription non autorisée.", 403)
                classroom = AcademicClass.objects.filter(school=school, pk=as_uuid(wanted["classroom"])).first()
                if classroom is None:
                    raise Refused("Classe introuvable.", 404)
                day = None
                if wanted.get("enrolled_on"):
                    day = parse_fields({"enrolled_on": wanted["enrolled_on"]}, ("enrolled_on",))["enrolled_on"]
                enrollment = enroll(school, request, student, classroom, day)
                if fees_wanted:
                    if has_permission(request.user, school, "school.finance.manage"):
                        charges = apply_fees(school, enrollment, request.user)
                    else:
                        fees_skipped = True
        return JsonResponse({
            "student": describe(student), "guardians": [describe(g) for g in saved_guardians],
            "enrollment": describe(enrollment) if enrollment else None,
            "charges_created": charges, "fees_skipped": fees_skipped,
        }, status=201)
    return respond(run)


@require_GET
@authorized
def next_code(request, school_id):
    school, error = gate(request, school_id, "school.students.manage")
    if error is not None:
        return error
    return JsonResponse({"student_code": next_student_code(school)})


@require_GET
@authorized
def student_dossier(request, school_id, student_id):
    """Fiche complète d'un élève : identité, responsables, parcours et paiements (si autorisé)."""
    school, error = gate(request, school_id, "school.students.read")
    if error is not None:
        return error
    student = Student.objects.filter(school=school, pk=student_id).first()
    if student is None:
        return JsonResponse({"error": "Élève introuvable."}, status=404)
    finance_visible = has_permission(request.user, school, "school.finance.read")
    rows = list(Enrollment.objects.select_related("year", "classroom").filter(school=school, student=student).order_by("-year__start_date"))
    enrollments = []
    for e in rows:
        item = {**describe(e), "year_name": e.year.name, "classroom_name": e.classroom.name}
        if finance_visible:
            charges = list(FeeCharge.objects.filter(school=school, enrollment=e).order_by("due_date", "created_at"))
            payments = list(FeePayment.objects.select_related("charge").filter(school=school, charge__enrollment=e)
                            .order_by("-paid_on", "-created_at"))
            voided = set(FeePayment.objects.filter(pk__in=[p.pk for p in payments], void__isnull=False).values_list("pk", flat=True))
            paid = Counter()
            for p in payments:
                if p.pk not in voided:
                    paid[p.charge_id] += p.amount
            billed_total = sum((c.amount for c in charges), ZERO)
            paid_total = sum(paid.values(), ZERO)
            item["finance"] = {
                "currency": charges[0].currency if charges else None,
                "billed": money(billed_total), "paid": money(paid_total), "balance": money(billed_total - paid_total),
                "status": finance_status({"billed": billed_total, "paid": paid_total}),
                "charges": [{"id": str(c.pk), "label": c.label, "amount": money(c.amount), "currency": c.currency,
                             "due_date": c.due_date.isoformat() if c.due_date else None,
                             "paid": money(paid[c.pk]), "balance": money(c.amount - paid[c.pk])} for c in charges],
                "payments": [{"id": str(p.pk), "label": p.charge.label, "amount": money(p.amount), "currency": p.currency,
                              "method": p.method, "reference": p.reference, "paid_on": p.paid_on.isoformat(),
                              "voided": p.pk in voided} for p in payments],
            }
        enrollments.append(item)
    config, _ = load_config(school)
    return JsonResponse({
        "student": describe(student),
        "form": config,
        "missing_documents": missing_documents(config, student.documents),
        "guardians": [describe(g) for g in student.guardians.order_by("-is_primary", "full_name")[:20]],
        "enrollments": enrollments,
        "finance_visible": finance_visible,
    })


@require_GET
@authorized
def classes_overview(request, school_id):
    """Classes d'une année avec effectifs, places restantes et, si autorisé, situation financière."""
    school, error = gate(request, school_id, "school.academic.read")
    if error is not None:
        return error
    year = current_year(school, request.GET.get("year") or None)
    years = AcademicYear.objects.filter(school=school).order_by("-start_date")
    levels = AcademicLevel.objects.select_related("cycle").filter(school=school).order_by("cycle__order", "order", "name")
    classes = list(AcademicClass.objects.select_related("level").filter(school=school, year=year).order_by("level__order", "name")) if year else []
    enrollments = list(Enrollment.objects.filter(school=school, year=year, active=True)) if year else []
    counts = Counter(e.classroom_id for e in enrollments)
    finance_visible = has_permission(request.user, school, "school.finance.read")
    currency, balances = enrollment_balances(school, [e.pk for e in enrollments]) if finance_visible else (None, {})
    per_class = {}
    for e in enrollments:
        b = balances.get(e.pk)
        f = per_class.setdefault(e.classroom_id, {"billed": ZERO, "paid": ZERO, "a_jour": 0, "partiel": 0, "impaye": 0, "sans_frais": 0})
        if b:
            f["billed"] += b["billed"]
            f["paid"] += b["paid"]
        f[finance_status(b)] += 1
    schedules = Counter()
    if year and finance_visible:
        for cid in FeeSchedule.objects.filter(school=school, year=year, active=True).values_list("classroom_id", flat=True):
            schedules[cid] += 1
    unassigned = Student.objects.filter(school=school, active=True).exclude(enrollments__year=year).count() if year else 0
    return JsonResponse({
        "year": {"id": str(year.pk), "name": year.name, "start_date": year.start_date.isoformat(), "end_date": year.end_date.isoformat()} if year else None,
        "years": [{"id": str(y.pk), "name": y.name, "active": y.active} for y in years],
        "levels": [{"id": str(lv.pk), "name": lv.name, "cycle": lv.cycle.name, "active": lv.active} for lv in levels],
        "currency": currency or "XAF",
        "finance_visible": finance_visible,
        "unassigned_students": unassigned,
        "can_manage_academic": has_permission(request.user, school, "school.academic.manage"),
        "can_manage_students": has_permission(request.user, school, "school.students.manage"),
        "can_manage_finance": has_permission(request.user, school, "school.finance.manage"),
        "classes": [{
            "id": str(c.pk), "name": c.name, "code": c.code, "active": c.active, "revision": c.revision,
            "level": {"id": str(c.level_id), "name": c.level.name},
            "capacity": c.capacity, "enrolled": counts[c.pk],
            "remaining": (c.capacity - counts[c.pk]) if c.capacity is not None else None,
            "fee_schedules": (schedules[c.pk] + schedules[None]) if finance_visible else None,
            "finance": ({k: (money(v) if isinstance(v, Decimal) else v) for k, v in per_class.get(c.pk, {}).items()}
                        | {"balance": money(per_class.get(c.pk, {}).get("billed", ZERO) - per_class.get(c.pk, {}).get("paid", ZERO))}
                        if finance_visible else None),
        } for c in classes],
    })


@require_POST
@authorized
def quick_classes(request, school_id):
    """Crée une ou plusieurs classes d'un coup ; le niveau (et son cycle) peut être créé à la volée."""
    school, error = gate(request, school_id, "school.academic.manage")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error

    def run():
        if not isinstance(data, dict) or set(data) - {"year", "level", "level_name", "cycle_name", "names", "capacity"}:
            raise Refused("Champs inconnus.")
        year = AcademicYear.objects.filter(school=school, pk=as_uuid(data.get("year"))).first()
        if year is None:
            raise Refused("Année scolaire introuvable.", 404)
        if not year.active:
            raise Refused("Année scolaire archivée.")
        names = data.get("names")
        if isinstance(names, str):
            names = re.split(r"[,;\n]", names)
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise Refused("Noms de classes invalides.")
        names = list(dict.fromkeys(n.strip() for n in names if n.strip()))
        if not 1 <= len(names) <= 30 or any(len(n) > 120 for n in names):
            raise Refused("Indiquez entre 1 et 30 noms de classe (120 caractères au plus).")
        capacity = data.get("capacity")
        if capacity in ("", None):
            capacity = None
        elif type(capacity) is not int or not 1 <= capacity <= 5000:
            raise Refused("Capacité invalide (1 à 5000).")
        with transaction.atomic():
            if data.get("level"):
                level = AcademicLevel.objects.filter(school=school, pk=as_uuid(data["level"])).first()
                if level is None:
                    raise Refused("Niveau introuvable.", 404)
            else:
                level_name = str(data.get("level_name") or "").strip()
                if not 1 <= len(level_name) <= 120:
                    raise Refused("Choisissez un niveau ou saisissez son nom.")
                level = AcademicLevel.objects.filter(school=school, name__iexact=level_name).first()
                if level is None:
                    cycle_name = str(data.get("cycle_name") or "").strip()[:120] or "Cycle principal"
                    cycle = AcademicCycle.objects.filter(school=school, name__iexact=cycle_name).first()
                    if cycle is None:
                        taken = set(AcademicCycle.objects.filter(school=school).values_list("code", flat=True))
                        cycle = AcademicCycle(school=school, code=unique_code(cycle_name, taken), name=cycle_name,
                                              order=AcademicCycle.objects.filter(school=school).count())
                        cycle.full_clean()
                        cycle.save()
                        log_event(school, request, "academic_cycles_created", cycle.pk)
                    taken = set(AcademicLevel.objects.filter(school=school).values_list("code", flat=True))
                    level = AcademicLevel(school=school, cycle=cycle, code=unique_code(level_name, taken), name=level_name,
                                          order=AcademicLevel.objects.filter(school=school).count())
                    level.full_clean()
                    level.save()
                    log_event(school, request, "academic_levels_created", level.pk)
            existing = {n.lower() for n in AcademicClass.objects.filter(school=school, year=year).values_list("name", flat=True)}
            duplicates = [n for n in names if n.lower() in existing]
            if duplicates:
                raise Refused("Classe déjà existante pour cette année : " + ", ".join(duplicates), 409)
            taken = set(AcademicClass.objects.filter(school=school, year=year).values_list("code", flat=True))
            created = []
            for name in names:
                code = unique_code(name, taken)
                taken.add(code)
                row = AcademicClass(school=school, year=year, level=level, code=code, name=name, capacity=capacity)
                row.full_clean()
                row.save()
                log_event(school, request, "academic_classes_created", row.pk)
                created.append({"id": str(row.pk), "name": row.name, "code": row.code})
        return JsonResponse({"level": {"id": str(level.pk), "name": level.name}, "classes": created}, status=201)
    return respond(run)


@require_POST
@authorized
def class_enroll(request, school_id, class_id):
    """Inscrit plusieurs élèves existants dans une classe ; chaque élève est traité séparément."""
    school, error = gate(request, school_id, "school.students.manage")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) - {"students", "enrolled_on", "apply_fees"}:
        return JsonResponse({"error": "Champs inconnus."}, status=422)
    ids = data.get("students")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 200:
        return JsonResponse({"error": "Sélectionnez entre 1 et 200 élèves."}, status=422)
    fees_wanted = data.get("apply_fees", True) is True
    can_bill = has_permission(request.user, school, "school.finance.manage")
    day = None
    try:
        if data.get("enrolled_on"):
            day = parse_fields({"enrolled_on": data["enrolled_on"]}, ("enrolled_on",))["enrolled_on"]
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    if not AcademicClass.objects.filter(school=school, pk=class_id).exists():
        return JsonResponse({"error": "Classe introuvable."}, status=404)
    done, failed, charges = [], [], 0
    for raw in ids:
        try:
            with transaction.atomic():
                student = Student.objects.filter(school=school, pk=as_uuid(raw)).first()
                if student is None:
                    raise Refused("Élève introuvable.", 404)
                classroom = AcademicClass.objects.get(school=school, pk=class_id)
                record = enroll(school, request, student, classroom, day)
                if fees_wanted and can_bill:
                    charges += apply_fees(school, record, request.user)
                done.append(str(student.pk))
        except (Refused, ValidationError, IntegrityError, ValueError) as exc:
            message = str(exc) if isinstance(exc, (Refused, ValueError)) else "Inscription refusée."
            if isinstance(exc, ValidationError):
                message = " ".join(exc.messages)[:200]
            failed.append({"student": str(raw), "error": message})
    return JsonResponse({"enrolled": done, "failed": failed, "charges_created": charges,
                         "fees_skipped": fees_wanted and not can_bill}, status=201 if done else 422)


@require_POST
@authorized
def class_apply_fees(request, school_id, class_id):
    """Affecte les barèmes applicables à tous les inscrits actifs d'une classe (sans doublon)."""
    school, error = gate(request, school_id, "school.finance.manage")
    if error is not None:
        return error
    classroom = AcademicClass.objects.filter(school=school, pk=class_id).first()
    if classroom is None:
        return JsonResponse({"error": "Classe introuvable."}, status=404)

    def run():
        created = 0
        with transaction.atomic():
            for e in Enrollment.objects.select_for_update().filter(school=school, classroom=classroom, active=True, student__active=True):
                created += apply_fees(school, e, request.user)
            if created:
                log_event(school, request, "fee_charge_created", classroom.pk)
        return JsonResponse({"charges_created": created})
    return respond(run)
