"""M2.7: safe, auditable class-division assignments for an enrolled learner."""
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import AcademicClass, AcademicYear
from .models import School
from .services import has_permission
from .student_models import Enrollment, EnrollmentEvent
from .student_views import describe, validate_enrollment_slot
from .views import access, log_event, parse_body, refuse


def eligible_divisions(enrollment):
    """A division change must not silently alter an academic level or track."""
    current = enrollment.classroom
    return AcademicClass.objects.filter(
        school_id=enrollment.school_id, year_id=enrollment.year_id,
        level_id=current.level_id, track_id=current.track_id, active=True,
        level__active=True, level__cycle__active=True,
    ).filter(Q(track__isnull=True) | Q(track__active=True)).order_by("pk")


def possibilities(enrollment, *, locked=False):
    queryset = eligible_divisions(enrollment)
    if locked:
        queryset = queryset.select_for_update()
    classes = list(queryset)
    # Counting while holding the candidate row locks ensures that two
    # simultaneous assignments cannot both take the final place.
    from django.db.models import Count
    counts = dict(
        Enrollment.objects.filter(school_id=enrollment.school_id, active=True,
                                  classroom_id__in=[c.pk for c in classes])
        .values("classroom_id").annotate(total=Count("pk"))
        .values_list("classroom_id", "total")
    )
    rows = []
    for room in classes:
        occupied = counts.get(room.pk, 0)
        remaining = None if room.capacity is None else max(0, room.capacity - occupied)
        rows.append((room, occupied, remaining))
    return rows


def serialize_options(enrollment):
    active = (enrollment.active and enrollment.student.active and enrollment.year.active
              and enrollment.year.status != AcademicYear.STATUS_CLOSED)
    options = possibilities(enrollment) if active else []
    return {
        "enrollment": str(enrollment.pk),
        "revision": enrollment.revision,
        "year": str(enrollment.year_id),
        "current_classroom": str(enrollment.classroom_id),
        "read_only": not active,
        "divisions": [
            {"id": str(room.pk), "name": room.name, "capacity": room.capacity,
             "occupied": occupied, "remaining": remaining}
            for room, occupied, remaining in options if room.pk != enrollment.classroom_id
        ],
    }


@require_http_methods(["GET", "POST"])
@authorized
def assignment(request, school_id, enrollment_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.students.manage"):
        return refuse()

    if request.method == "GET":
        record = Enrollment.objects.select_related(
            "student", "year", "classroom"
        ).filter(school=school, pk=enrollment_id).first()
        if record is None:
            return JsonResponse({"error": "Inscription introuvable."}, status=404)
        return JsonResponse(serialize_options(record), headers={"Cache-Control": "no-store"})

    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) not in ({"revision", "mode", "reason"}, {"revision", "mode", "reason", "classroom"}):
        return JsonResponse({"error": "Révision, mode et motif obligatoires."}, status=422)
    if type(data.get("revision")) is not int or data["revision"] < 1:
        return JsonResponse({"error": "Révision obligatoire."}, status=422)
    mode, reason = data.get("mode"), data.get("reason")
    if mode not in ("manual", "automatic"):
        return JsonResponse({"error": "Mode d'affectation invalide."}, status=422)
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 300 or any(ord(c) < 32 for c in reason):
        return JsonResponse({"error": "Motif requis, entre 5 et 300 caractères."}, status=422)
    reason = reason.strip()
    if (mode == "manual") != ("classroom" in data):
        return JsonResponse({"error": "Classe requise uniquement pour l'affectation manuelle."}, status=422)
    target_id = None
    if mode == "manual":
        try:
            target_id = UUID(data["classroom"]) if isinstance(data["classroom"], str) else None
        except ValueError:
            pass
        if target_id is None:
            return JsonResponse({"error": "Classe cible invalide."}, status=422)

    with transaction.atomic():
        # Use a common school lock to serialize assignments with enrolment
        # intake, and class row locks to serialize seat counts with class edits.
        School.objects.select_for_update().get(pk=school.pk)
        record = Enrollment.objects.select_for_update().select_related(
            "student", "year", "classroom"
        ).filter(school=school, pk=enrollment_id).first()
        if record is None:
            return JsonResponse({"error": "Inscription introuvable."}, status=404)
        if record.revision != data["revision"]:
            return JsonResponse({"error": "Conflit de version.", "revision": record.revision}, status=409)
        if (not record.active or not record.student.active or not record.year.active
                or record.year.status == AcademicYear.STATUS_CLOSED):
            return JsonResponse({"error": "Année clôturée ou inscription inactive : affectation interdite."}, status=409)
        choices = possibilities(record, locked=True)
        options = [
            (room, occupied, remaining) for room, occupied, remaining in choices
            if room.pk != record.classroom_id and (remaining is None or remaining > 0)
        ]
        if mode == "manual":
            chosen = next((x for x in choices if x[0].pk == target_id), None)
            if chosen is None or target_id == record.classroom_id:
                return JsonResponse({"error": "Choisissez une autre division ouverte du même niveau et de la même série."}, status=422)
            if chosen[2] == 0:
                return JsonResponse({"error": "Capacité de la classe atteinte."}, status=409)
        else:
            if not options:
                return JsonResponse({"error": "Aucune autre division compatible ne dispose de place."}, status=409)
            # Balance headcounts; stable name/UUID ordering resolves ties.
            chosen = min(options, key=lambda row: (row[1], row[0].name.casefold(), str(row[0].pk)))
        target, occupied, remaining = chosen
        try:
            validate_enrollment_slot(target, record.student, record.year, enrollment=record)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        previous_id = record.classroom_id
        record.classroom = target
        record.revision += 1
        record.full_clean()
        record.save(update_fields=["classroom", "revision"])
        EnrollmentEvent.objects.create(
            school=school, enrollment=record, actor=request.user,
            previous_class_id=previous_id, new_class_id=target.pk,
            previous_status=record.status, new_status=record.status,
            assignment_mode=mode, reason=reason,
        )
        log_event(school, request, "class_assignment_changed", record.pk, {
            "from_class": str(previous_id), "to_class": str(target.pk),
            "mode": mode, "reason": reason, "revision": record.revision,
        })
        return JsonResponse({
            "enrollment": describe(record),
            "assignment": {"from_class": str(previous_id), "to_class": str(target.pk),
                           "class_name": target.name, "mode": mode, "reason": reason},
        })
