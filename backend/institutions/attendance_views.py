"""Module 12: scoped class registers with configurable statuses and audit trails."""
import re
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import authorized

from .academic_models import AcademicClass
from .attendance_models import AttendanceSession, AttendanceMark, AttendanceChange
from .staff_models import StaffAssignment
from .student_models import Enrollment
from .services import has_permission, resolve_settings
from .views import access, refuse, parse_body, log_event

CODE = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
GROUPS = frozenset({"present", "absent", "late", "other"})


def uuid_value(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def text_field(value, maximum, required=False):
    if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
        raise ValueError("Texte invalide.")
    return value.strip()


def iso_date(value):
    if not isinstance(value, str):
        raise ValueError("Date ISO requise.")
    try:
        d = date.fromisoformat(value)
        if d.isoformat() != value:
            raise ValueError()
        return d
    except ValueError:
        raise ValueError("Date ISO invalide.") from None


def scoped(request, school_id):
    return access(request, school_id)


def assigned_to(user, school, classroom):
    return StaffAssignment.objects.filter(
        school=school, classroom=classroom, year_id=classroom.year_id, active=True,
        staff__school=school, staff__account=user, staff__active=True,
    ).exists()


def authorized_for(user, school, classroom, action):
    permission = {
        "read": "school.attendance.read", "write": "school.attendance.write",
        "finalize": "school.attendance.finalize",
    }[action]
    if has_permission(user, school, permission):
        return True
    return action in ("read", "write") and assigned_to(user, school, classroom)


def configured_statuses(school, classroom):
    context = {
        "year": classroom.year.code, "cycle": classroom.level.cycle.code,
        "level": classroom.level.code, "class": classroom.code,
    }
    settings = resolve_settings(school, context)[0].get("attendance", {})
    if not isinstance(settings, dict):
        raise ValueError("Configuration de présence invalide.")
    statuses = settings.get("statuses")
    if not isinstance(statuses, list) or not 1 <= len(statuses) <= 30:
        raise ValueError("Configurez attendance.statuses dans les paramètres de l'école.")
    mapping = {}
    for row in statuses:
        if not isinstance(row, dict) or set(row) != {"code", "label", "group"}:
            raise ValueError("Un statut de présence doit contenir code, label et group.")
        code, label, group = row["code"], row["label"], row["group"]
        if not isinstance(code, str) or not CODE.fullmatch(code):
            raise ValueError("Code de présence invalide.")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120:
            raise ValueError("Libellé de présence invalide.")
        if not isinstance(group, str) or group not in GROUPS or code in mapping:
            raise ValueError("Catégorie de présence invalide ou statut dupliqué.")
        mapping[code] = {"code": code, "label": label.strip(), "group": group}
    return mapping


def session_data(row):
    return {
        "id": str(row.pk), "classroom": str(row.classroom_id),
        "date": row.attendance_date.isoformat(), "slot": row.slot,
        "label": row.label, "revision": row.revision,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def mark_snapshot(row):
    return {
        "status": row.status_code, "label": row.status_label, "group": row.status_group,
        "note": row.note, "justification": row.justification,
        "justified": row.justified,
    }


def mark_data(row):
    return {
        "id": str(row.pk), "enrollment": str(row.enrollment_id),
        "revision": row.revision, **mark_snapshot(row),
    }


def choose_class(school, value):
    uid = uuid_value(value)
    if uid is None:
        return None
    return AcademicClass.objects.select_related("year", "level__cycle").filter(
        school=school, pk=uid
    ).first()


def choose_session(school, value):
    return AttendanceSession.objects.select_related(
        "classroom__year", "classroom__level__cycle"
    ).filter(school=school, pk=value).first()


def eligible_enrollments(school, session):
    return Enrollment.objects.select_related("student").filter(
        school=school, year=session.classroom.year, classroom=session.classroom,
        active=True, student__active=True, enrolled_on__lte=session.attendance_date,
    ).order_by("student__last_name", "student__first_name", "pk")


@require_GET
@authorized
def options(request, school_id):
    school, error = scoped(request, school_id)
    if error is not None:
        return error
    classroom = choose_class(school, request.GET.get("classroom"))
    if classroom is None:
        return JsonResponse({"error": "Classe introuvable."}, status=404)
    if not authorized_for(request.user, school, classroom, "read"):
        return refuse()
    try:
        statuses = configured_statuses(school, classroom)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    return JsonResponse({"statuses": list(statuses.values())})


@require_http_methods(["GET", "POST"])
@authorized
def sessions(request, school_id):
    school, error = scoped(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        classroom = choose_class(school, request.GET.get("classroom"))
        if classroom is None:
            return JsonResponse({"error": "Classe introuvable."}, status=404)
        if not authorized_for(request.user, school, classroom, "read"):
            return refuse()
        rows = AttendanceSession.objects.filter(school=school, classroom=classroom).order_by(
            "-attendance_date", "slot"
        )[:200]
        return JsonResponse({"sessions": [session_data(item) for item in rows]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"classroom", "date", "slot", "label"}:
        return JsonResponse({"error": "Champs de séance invalides."}, status=422)
    classroom = choose_class(school, data["classroom"])
    if classroom is None:
        return JsonResponse({"error": "Classe introuvable."}, status=404)
    if not authorized_for(request.user, school, classroom, "write"):
        return refuse()
    try:
        attendance_date = iso_date(data["date"])
        slot = data["slot"]
        if not isinstance(slot, str) or not CODE.fullmatch(slot):
            raise ValueError("Code de séance invalide.")
        label = text_field(data["label"], 120, required=True)
        configured_statuses(school, classroom)
        if not classroom.active or not classroom.year.active:
            raise ValueError("Classe ou année scolaire inactive.")
        with transaction.atomic():
            row = AttendanceSession(
                school=school, classroom=classroom, attendance_date=attendance_date,
                slot=slot, label=label, created_by=request.user,
            )
            row.full_clean()
            row.save()
            log_event(school, request, "attendance_session_created", row.pk)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except ValidationError as exc:
        return JsonResponse({"error": "Séance incohérente avec l'année scolaire."}, status=422)
    except IntegrityError:
        return JsonResponse({"error": "Un appel existe déjà pour cette classe, date et séance."}, status=409)
    return JsonResponse(session_data(row), status=201)


@require_GET
@authorized
def session_detail(request, school_id, session_id):
    school, error = scoped(request, school_id)
    if error is not None:
        return error
    session = choose_session(school, session_id)
    if session is None:
        return JsonResponse({"error": "Séance introuvable."}, status=404)
    if not authorized_for(request.user, school, session.classroom, "read"):
        return refuse()
    roster = list(eligible_enrollments(school, session))
    entries = {item.enrollment_id: item for item in AttendanceMark.objects.filter(
        school=school, session=session, enrollment__in=roster
    )}
    return JsonResponse({
        **session_data(session),
        "roster": [
            {
                "enrollment": str(e.pk), "student_code": e.student.student_code,
                "first_name": e.student.first_name, "last_name": e.student.last_name,
                "mark": mark_data(entries[e.pk]) if e.pk in entries else None,
            } for e in roster
        ],
    })


@require_POST
@authorized
def record_marks(request, school_id, session_id):
    school, error = scoped(request, school_id)
    if error is not None:
        return error
    session = choose_session(school, session_id)
    if session is None:
        return JsonResponse({"error": "Séance introuvable."}, status=404)
    if not authorized_for(request.user, school, session.classroom, "write"):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"marks"} or not isinstance(data["marks"], list) or not 1 <= len(data["marks"]) <= 100:
        return JsonResponse({"error": "Lot invalide (1 à 100 inscriptions)."}, status=422)
    try:
        catalog = configured_statuses(school, session.classroom)
        pending = []
        seen = set()
        for item in data["marks"]:
            if not isinstance(item, dict) or set(item) != {
                "enrollment", "status", "note", "justification", "justified", "revision", "reason"
            }:
                raise ValueError("Champs de présence invalides.")
            enrollment = uuid_value(item["enrollment"])
            if enrollment is None or enrollment in seen:
                raise ValueError("Inscription invalide ou répétée.")
            seen.add(enrollment)
            code = item["status"]
            if not isinstance(code, str) or code not in catalog:
                raise ValueError("Statut non autorisé dans cette école.")
            revision = item["revision"]
            if type(revision) is not int or revision < 0:
                raise ValueError("Révision invalide.")
            note = text_field(item["note"], 500)
            justification = text_field(item["justification"], 500)
            reason = text_field(item["reason"], 500)
            justified = item["justified"]
            if type(justified) is not bool or (justified and not justification):
                raise ValueError("Justification invalide.")
            if justified and not has_permission(request.user, school, "school.attendance.write"):
                raise ValueError("La validation des justificatifs exige une permission d'établissement.")
            pending.append((enrollment, catalog[code], revision, note, justification, justified, reason))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    with transaction.atomic():
        session = AttendanceSession.objects.select_for_update().get(school=school, pk=session_id)
        if session.closed_at:
            return JsonResponse({"error": "Appel clôturé, aucune correction possible."}, status=409)
        allowed_ids = set(eligible_enrollments(school, session).values_list("pk", flat=True))
        if any(uid not in allowed_ids for uid, *_ in pending):
            return JsonResponse({"error": "Élève hors de cette classe ou inscrit après la séance."}, status=422)
        prior = {x.enrollment_id: x for x in AttendanceMark.objects.select_for_update().filter(
            school=school, session=session, enrollment_id__in=seen
        )}
        for uid, policy, revision, note, justification, justified, reason in pending:
            current = prior.get(uid)
            if current and current.justified != justified and not has_permission(request.user, school, "school.attendance.write"):
                return refuse()
            current_revision = current.revision if current else 0
            if revision != current_revision:
                return JsonResponse({"error": "Conflit de version.", "enrollment": str(uid),
                                     "revision": current_revision}, status=409)
            if current and not reason:
                new_snapshot = {"status": policy["code"], "label": policy["label"], "group": policy["group"],
                                "note": note, "justification": justification, "justified": justified}
                if new_snapshot != mark_snapshot(current):
                    return JsonResponse({"error": "Une correction doit avoir un motif."}, status=422)
        updated = []
        for uid, policy, revision, note, justification, justified, reason in pending:
            row = prior.get(uid)
            old = mark_snapshot(row) if row else None
            new = {"status": policy["code"], "label": policy["label"], "group": policy["group"],
                   "note": note, "justification": justification, "justified": justified}
            if old == new:
                updated.append(mark_data(row))
                continue
            if row is None:
                row = AttendanceMark(
                    school=school, session=session, enrollment_id=uid,
                    status_code=policy["code"], status_label=policy["label"],
                    status_group=policy["group"], note=note, justification=justification,
                    justified=justified, updated_by=request.user,
                )
            else:
                row.status_code = policy["code"]
                row.status_label = policy["label"]
                row.status_group = policy["group"]
                row.note = note
                row.justification = justification
                row.justified = justified
                row.updated_by = request.user
                row.revision += 1
            row.full_clean()
            row.save()
            change = AttendanceChange(
                school=school, mark=row, revision=row.revision,
                before=old, after=new, reason=reason, actor=request.user,
            )
            change.full_clean()
            change.save()
            updated.append(mark_data(row))
        session.revision += 1
        session.save(update_fields=["revision"])
        log_event(school, request, "attendance_marks_recorded", session.pk)
    return JsonResponse({"marks": updated, "session_revision": session.revision})


@require_POST
@authorized
def close_session(request, school_id, session_id):
    school, error = scoped(request, school_id)
    if error is not None:
        return error
    session = choose_session(school, session_id)
    if session is None:
        return JsonResponse({"error": "Séance introuvable."}, status=404)
    if not authorized_for(request.user, school, session.classroom, "finalize"):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"revision"} or type(data["revision"]) is not int or data["revision"] < 1:
        return JsonResponse({"error": "Révision de séance obligatoire."}, status=422)
    with transaction.atomic():
        session = AttendanceSession.objects.select_for_update().get(school=school, pk=session_id)
        if session.closed_at:
            return JsonResponse({"error": "Appel déjà clôturé."}, status=409)
        if session.revision != data["revision"]:
            return JsonResponse({"error": "Conflit de version.", "revision": session.revision}, status=409)
        roster = eligible_enrollments(school, session)
        needed = roster.count()
        marked = AttendanceMark.objects.filter(school=school, session=session, enrollment__in=roster).count()
        if needed == 0 or marked != needed:
            return JsonResponse({"error": "Chaque élève inscrit doit être renseigné avant clôture.",
                                 "expected": needed, "marked": marked}, status=422)
        session.closed_at = timezone.now()
        session.closed_by = request.user
        session.revision += 1
        session.save(update_fields=["closed_at", "closed_by", "revision"])
        log_event(school, request, "attendance_session_closed", session.pk)
    return JsonResponse(session_data(session))


@require_GET
@authorized
def changes(request, school_id, session_id, enrollment_id):
    school, error = scoped(request, school_id)
    if error is not None:
        return error
    session = choose_session(school, session_id)
    if session is None:
        return JsonResponse({"error": "Séance introuvable."}, status=404)
    if not authorized_for(request.user, school, session.classroom, "read"):
        return refuse()
    row = AttendanceMark.objects.filter(
        school=school, session=session, enrollment_id=enrollment_id
    ).first()
    if row is None:
        return JsonResponse({"error": "Saisie introuvable."}, status=404)
    result = AttendanceChange.objects.filter(school=school, mark=row).select_related("actor").order_by("revision")[:100]
    return JsonResponse({"history": [{
        "revision": item.revision, "before": item.before, "after": item.after,
        "reason": item.reason, "actor": str(item.actor_id) if item.actor_id else None,
        "created_at": item.created_at.isoformat(),
    } for item in result]})


@require_GET
@authorized
def summary(request, school_id):
    school, error = scoped(request, school_id)
    if error is not None:
        return error
    classroom = choose_class(school, request.GET.get("classroom"))
    if classroom is None:
        return JsonResponse({"error": "Classe introuvable."}, status=404)
    if not authorized_for(request.user, school, classroom, "read"):
        return refuse()
    try:
        start = iso_date(request.GET.get("from"))
        end = iso_date(request.GET.get("to"))
        if start > end or start < classroom.year.start_date or end > classroom.year.end_date:
            raise ValueError("Dates hors de l'année scolaire.")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    rows = AttendanceMark.objects.filter(
        school=school, session__classroom=classroom,
        session__attendance_date__gte=start, session__attendance_date__lte=end,
    ).values_list("status_group", flat=True)
    totals = {group: 0 for group in sorted(GROUPS)}
    recorded = 0
    for group in rows:
        totals[group] = totals.get(group, 0) + 1
        recorded += 1
    sessions_count = AttendanceSession.objects.filter(
        school=school, classroom=classroom,
        attendance_date__gte=start, attendance_date__lte=end
    ).count()
    return JsonResponse({"classroom": str(classroom.pk), "from": start.isoformat(),
                         "to": end.isoformat(), "sessions": sessions_count,
                         "recorded": recorded, "groups": totals})
