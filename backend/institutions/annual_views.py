"""Annual academic workspace.

A school year is a historical partition, not another instance of YEM.
Preparing a year may copy class *structure*, never pupils, grades, payments,
reports, timetables or staff assignments from the source year.
"""
import re
from datetime import date
from uuid import UUID

from accounts.views import authorized
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction, connection
from django.db.models import Count
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .academic_models import AcademicYear, AcademicYearClosure, AcademicClass, AcademicPeriod
from .standard_classes import ensure_standard_classes
from .assessment_models import Assessment
from .models import School
from .report_models import SchoolReport
from .staff_models import StaffAssignment
from .student_models import Enrollment
from .cycle_scope import scoped_cycle_ids
from .year_closure import annual_closure_checks, annual_closure_snapshot, closure_fingerprint
from .services import has_permission
from .views import access, log_event, parse_body, refuse


def _year_id(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _year_dict(year):
    return {
        "id": str(year.pk), "code": year.code, "name": year.name,
        "start_date": year.start_date.isoformat(), "end_date": year.end_date.isoformat(),
        "active": year.active, "status": year.status, "revision": year.revision,
    }


@require_GET
@authorized
def annual_snapshot(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.academic.read"):
        return refuse()

    years = AcademicYear.objects.filter(school=school).order_by("-start_date", "pk")
    selected = request.GET.get("year")
    if selected:
        year_id = _year_id(selected)
        year = years.filter(pk=year_id).first() if year_id else None
        if year is None:
            return JsonResponse({"error": "Année scolaire introuvable dans cet établissement."}, status=422)
    else:
        from .overview_views import current_year
        year = current_year(school)

    result = {
        "years": [_year_dict(item) for item in years[:100]],
        "year": _year_dict(year) if year else None,
        "can_edit_year": bool(year and year.active and year.status != AcademicYear.STATUS_CLOSED
            and has_permission(request.user, school, "school.academic.manage")
            and scoped_cycle_ids(request.user, school) is None),
        "can_prepare_year": has_permission(request.user, school, "school.academic.manage")
                            and scoped_cycle_ids(request.user, school) is None,
        "can_activate_year": bool(
            year is not None and year.active and year.status == AcademicYear.STATUS_PREPARATION
            and has_permission(request.user, school, "school.academic.manage")
            and scoped_cycle_ids(request.user, school) is None
            and not years.filter(status=AcademicYear.STATUS_CURRENT).exists()
        ),
        "classes": [],
        "periods": [],
        "stats": {},
    }
    if year is None:
        return JsonResponse(result)

    classes = AcademicClass.objects.select_related("level__cycle", "track").filter(
        school=school, year=year
    ).order_by("level__order", "name", "pk")
    scope = scoped_cycle_ids(request.user, school)
    if scope is not None:
        classes = classes.filter(level__cycle_id__in=scope)
    rooms = list(classes[:500])
    room_ids = [room.pk for room in rooms]

    can_students = has_permission(request.user, school, "school.students.read")
    can_reports = has_permission(request.user, school, "school.reports.read")
    can_staff = has_permission(request.user, school, "school.staff.read")
    can_assess = has_permission(request.user, school, "school.assessments.read")

    enrollments = dict(Enrollment.objects.filter(
        school=school, year=year, classroom_id__in=room_ids, active=True
    ).values_list("classroom_id").annotate(total=Count("pk"))) if can_students else {}
    reports = dict(SchoolReport.objects.filter(
        school=school, year=year, enrollment__classroom_id__in=room_ids,
        status="published"
    ).values_list("enrollment__classroom_id").annotate(total=Count("pk"))) if can_reports else {}
    assignments = dict(StaffAssignment.objects.filter(
        school=school, year=year, classroom_id__in=room_ids, active=True
    ).values_list("classroom_id").annotate(total=Count("pk"))) if can_staff else {}
    annual_team = {}
    if can_staff:
        for assignment in StaffAssignment.objects.select_related("staff").filter(
            school=school, year=year, classroom_id__in=room_ids, active=True
        ).order_by("staff__last_name", "staff__first_name", "duty"):
            annual_team.setdefault(assignment.classroom_id, []).append({
                "staff_id": str(assignment.staff_id),
                "name": f"{assignment.staff.first_name} {assignment.staff.last_name}".strip(),
                "duty": assignment.duty,
            })
    assessments = dict(Assessment.objects.filter(
        school=school, course__year=year, course__classroom_id__in=room_ids
    ).values_list("course__classroom_id").annotate(total=Count("pk"))) if can_assess else {}

    result["classes"] = [{
        "id": str(room.pk), "code": room.code, "name": room.name, "active": room.active,
        "level": room.level.name, "cycle": room.level.cycle.name,
        "track": room.track.name if room.track_id else None, "capacity": room.capacity,
        "enrolled": enrollments.get(room.pk) if can_students else None,
        "published_reports": reports.get(room.pk) if can_reports else None,
        "staff_assignments": assignments.get(room.pk) if can_staff else None,
        "team": annual_team.get(room.pk, []) if can_staff else None,
        "assessments": assessments.get(room.pk) if can_assess else None,
    } for room in rooms]

    result["periods"] = [{
        "id": str(p.pk), "revision": p.revision, "code": p.code, "name": p.name,
        "start_date": p.start_date.isoformat(), "end_date": p.end_date.isoformat(),
        "active": p.active,
    } for p in AcademicPeriod.objects.filter(school=school, year=year).order_by("order", "start_date")]
    result["stats"] = {
        "classes": len(rooms),
        "periods": len(result["periods"]),
        "enrollments": sum(enrollments.values()) if can_students else None,
        "published_reports": sum(reports.values()) if can_reports else None,
        "staff_assignments": sum(assignments.values()) if can_staff else None,
        "assessments": sum(assessments.values()) if can_assess else None,
    }
    return JsonResponse(result)


def _year_closure_authorized(request, school):
    return (has_permission(request.user, school, "school.academic.manage")
            and has_permission(request.user, school, "school.finance.read")
            and scoped_cycle_ids(request.user, school) is None)


@require_GET
@authorized
def closure_review(request, school_id, year_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not _year_closure_authorized(request, school):
        return refuse()
    year = AcademicYear.objects.filter(school=school, pk=year_id).first()
    if year is None:
        return JsonResponse({"error": "Année scolaire introuvable."}, status=404)
    evidence = AcademicYearClosure.objects.filter(school=school, year=year).first()
    snapshot = evidence.snapshot if evidence else annual_closure_snapshot(school, year)
    checks = {"ready": False, "blockers": [], "warnings": []} if evidence else annual_closure_checks(school, year)
    return JsonResponse({
        "year": _year_dict(year), "snapshot": snapshot,
        "checks": checks, "can_close": bool(
            checks["ready"] and getattr(settings, "YEM_YEAR_CLOSURE_ENABLED", False)
            and connection.vendor == "postgresql"
        ),
        "closure_enabled": bool(
            getattr(settings, "YEM_YEAR_CLOSURE_ENABLED", False)
            and connection.vendor == "postgresql"
        ),
        "evidence": ({
            "id": str(evidence.pk), "sha256": evidence.digest_sha256,
            "closed_at": evidence.closed_at.isoformat(),
            "closed_by": str(evidence.closed_by_id) if evidence.closed_by_id else None,
            "reason": evidence.reason,
            "integrity_ok": closure_fingerprint(evidence.snapshot) == evidence.digest_sha256,
        } if evidence else None),
    })


@require_POST
@authorized
def close_year(request, school_id, year_id):
    """One-way, audited closure. Requires PostgreSQL row triggers and manual opt-in."""
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not _year_closure_authorized(request, school):
        return refuse()
    if (not getattr(settings, "YEM_YEAR_CLOSURE_ENABLED", False)
            or connection.vendor != "postgresql"):
        return JsonResponse({
            "error": "Clôture définitive désactivée : sauvegarde réelle et contrôles PostgreSQL requis."
        }, status=503)
    body, error = parse_body(request)
    if error is not None:
        return error
    if set(body) != {"revision", "confirmation", "reason"}:
        return JsonResponse({"error": "Révision, code d'année et motif obligatoires."}, status=422)
    revision, reason, confirmation = body["revision"], body["reason"], body["confirmation"]
    if (type(revision) is not int or revision < 1
            or not isinstance(reason, str) or not 20 <= len(reason.strip()) <= 600
            or not isinstance(confirmation, str)):
        return JsonResponse({"error": "Révision valide et motif de 20 à 600 caractères requis."}, status=422)
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            year = AcademicYear.objects.select_for_update().filter(school=school, pk=year_id).first()
            if year is None:
                return JsonResponse({"error": "Année scolaire introuvable."}, status=404)
            if year.revision != revision:
                return JsonResponse({"error": "Conflit de version.", "revision": year.revision}, status=409)
            if confirmation != year.code:
                return JsonResponse({"error": "Le code de confirmation ne correspond pas à l'année."}, status=422)
            if AcademicYearClosure.objects.filter(year=year).exists():
                return JsonResponse({"error": "Cette année est déjà clôturée."}, status=409)
            checks = annual_closure_checks(school, year)
            if not checks["ready"]:
                return JsonResponse({"error": "Clôture refusée : contrôles non satisfaits.", "checks": checks}, status=409)
            snapshot = annual_closure_snapshot(school, year)
            digest = closure_fingerprint(snapshot)
            evidence = AcademicYearClosure(
                school=school, year=year, snapshot=snapshot, digest_sha256=digest,
                reason=reason.strip(), closed_by=request.user,
            )
            evidence.full_clean()
            evidence.save()
            year.status = AcademicYear.STATUS_CLOSED
            year.active = False
            year.revision += 1
            year.save(update_fields=["status", "active", "revision"])
            log_event(school, request, "academic_year_closed", str(year.pk), {
                "reason": reason.strip(), "digest_sha256": digest,
                "closure_id": str(evidence.pk), "status_from": "current", "status_to": "closed",
            })
    except (IntegrityError, ValidationError) as exc:
        return JsonResponse({"error": "Conflit de clôture ou données invalides."}, status=409)
    return JsonResponse({
        "year": _year_dict(year),
        "evidence": {"id": str(evidence.pk), "sha256": evidence.digest_sha256},
        "message": "Année scolaire définitivement clôturée et archivée.",
    })


@require_POST
@authorized
def activate_year(request, school_id, year_id):
    """Explicit, audited activation. Closing is intentionally not yet exposed.

    All year-dependent write endpoints must first honor closed status before
    allowing the school year to be finalized.
    """
    school, error = access(request, school_id)
    if error is not None:
        return error
    if (not has_permission(request.user, school, "school.academic.manage")
            or scoped_cycle_ids(request.user, school) is not None):
        return refuse()
    body, error = parse_body(request)
    if error is not None:
        return error
    if set(body) != {"revision", "reason"}:
        return JsonResponse({"error": "Révision et motif obligatoires."}, status=422)
    revision, reason = body["revision"], body["reason"]
    if (type(revision) is not int or revision < 1
            or not isinstance(reason, str) or not 8 <= len(reason.strip()) <= 300):
        return JsonResponse({"error": "Révision valide et motif de 8 à 300 caractères requis."}, status=422)
    try:
        with transaction.atomic():
            # Serialise activations for one school, even if the target years differ.
            School.objects.select_for_update().get(pk=school.pk)
            year = AcademicYear.objects.select_for_update().filter(
                school=school, pk=year_id
            ).first()
            if year is None:
                return JsonResponse({"error": "Année scolaire introuvable."}, status=404)
            if year.revision != revision:
                return JsonResponse({"error": "Conflit de version.", "revision": year.revision}, status=409)
            if year.status != AcademicYear.STATUS_PREPARATION or not year.active:
                return JsonResponse({"error": "Seule une année en préparation peut être activée."}, status=409)
            if AcademicYear.objects.filter(
                school=school, status=AcademicYear.STATUS_CURRENT
            ).exclude(pk=year.pk).exists():
                return JsonResponse({
                    "error": "Une autre année est en cours. Sa clôture sécurisée est nécessaire avant l'activation suivante."
                }, status=409)
            year.status = AcademicYear.STATUS_CURRENT
            year.revision += 1
            year.save(update_fields=["status", "revision"])
            log_event(school, request, "academic_year_activated", str(year.pk), {
                "reason": reason.strip(), "status_from": "preparation", "status_to": "current",
            })
    except IntegrityError:
        return JsonResponse({"error": "Une année scolaire est déjà en cours."}, status=409)
    return JsonResponse({"year": _year_dict(year), "message": "Année scolaire activée."})


@require_POST
@authorized
def prepare_year(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    # Creating a school-wide year cannot be done with cycle-scoped privileges.
    if not has_permission(request.user, school, "school.academic.manage") or (
        scoped_cycle_ids(request.user, school) is not None
    ):
        return refuse()
    body, error = parse_body(request)
    if error is not None:
        return error
    required = {"code", "name", "start_date", "end_date", "copy_classes", "source_year"}
    if not isinstance(body, dict) or set(body) != required:
        return JsonResponse({"error": "Paramètres de nouvelle année incomplets."}, status=422)
    code, name = body["code"], body["name"]
    if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", code):
        return JsonResponse({"error": "Code de l'année invalide."}, status=422)
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 120):
        return JsonResponse({"error": "Nom de l'année invalide."}, status=422)
    if type(body["copy_classes"]) is not bool:
        return JsonResponse({"error": "Option de reprise des classes invalide."}, status=422)
    try:
        start, end = date.fromisoformat(body["start_date"]), date.fromisoformat(body["end_date"])
        if (start.isoformat() != body["start_date"] or end.isoformat() != body["end_date"]
                or start >= end):
            raise ValueError()
    except (TypeError, ValueError):
        return JsonResponse({"error": "Dates de l'année scolaire invalides."}, status=422)
    source_id = _year_id(body["source_year"])
    if (body["copy_classes"] and source_id is None) or (
        body["source_year"] is not None and source_id is None
    ):
        return JsonResponse({"error": "Choisissez une année de référence valide."}, status=422)
    try:
        with transaction.atomic():
            # Serialize concurrent annual preparations and guard against duplicate cohorts.
            School.objects.select_for_update().get(pk=school.pk)
            years = AcademicYear.objects.filter(school=school)
            if years.filter(code=code).exists() or years.filter(name__iexact=name.strip()).exists():
                return JsonResponse({"error": "Cette année scolaire existe déjà."}, status=409)
            if years.filter(start_date__lte=end, end_date__gte=start).exists():
                return JsonResponse({"error": "Ces dates chevauchent une année existante."}, status=409)
            source = years.filter(pk=source_id).first() if source_id else None
            if body["copy_classes"] and not source:
                return JsonResponse({"error": "Année de référence introuvable dans cette école."}, status=422)
            year = AcademicYear(school=school, code=code, name=name.strip(),
                                start_date=start, end_date=end)
            year.full_clean()
            year.save()
            copied = 0
            if body["copy_classes"]:
                for old in AcademicClass.objects.filter(school=school, year=source, active=True):
                    room = AcademicClass(school=school, year=year, code=old.code, name=old.name,
                                         level=old.level, track=old.track,
                                         capacity=old.capacity, active=True)
                    room.full_clean()
                    room.save()
                    copied += 1
            generated = []
            if not body["copy_classes"]:
                generated = ensure_standard_classes(school, year)
                if generated:
                    log_event(school, request, "standard_classes_generated", str(year.pk), {
                        "class_ids": [str(room.pk) for room in generated],
                    })
            log_event(school, request, "academic_year_prepared", str(year.pk), {
                "source_year": str(source.pk) if source else None,
                "classes_copied": copied, "copy_classes": body["copy_classes"],
            })
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)[:500]}, status=422)
    except IntegrityError:
        return JsonResponse({"error": "Année ou classe déjà existante."}, status=409)
    return JsonResponse({
        "year": _year_dict(year), "classes_copied": copied, "classes_generated": len(generated),
        "message": "Année préparée. Les élèves, affectations, évaluations, bulletins, paiements et périodes n'ont pas été copiés.",
    }, status=201)
