"""Daily preschool follow-up, scoped to the school and the educator's group."""
from datetime import date

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import AcademicClass, AcademicYear
from .calendar_views import uid
from .cycle_scope import calendar_assignments, scoped_cycle_ids
from .preschool_followup_models import PreschoolObservation
from .services import has_permission
from .student_models import Enrollment
from .views import access, log_event, parse_body, refuse


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def followup(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.academic.read"):
        return refuse()

    rooms = AcademicClass.objects.filter(
        school=school, level__cycle__school=school, level__cycle__code="prescolaire",
        year__school=school, active=True,
    )
    allowed = scoped_cycle_ids(request.user, school)
    if allowed is not None:
        rooms = rooms.filter(level__cycle_id__in=allowed)
    if not has_permission(request.user, school, "school.academic.manage"):
        rooms = rooms.filter(pk__in=calendar_assignments(request.user, school).filter(duty="enseignant").values("classroom_id"))

    if request.method == "GET" and "classroom" not in request.GET:
        return JsonResponse({"classrooms": list(rooms.filter(
            year_id=uid(request.GET.get("year")),
        ).order_by("name", "pk").values("id", "name"))})

    if request.method == "POST":
        data, error = parse_body(request)
        if error is not None:
            return error
        if set(data) != {"classroom", "day", "enrollment", "revision", "observation"}:
            return JsonResponse({"error": "Champs de suivi invalides."}, status=422)
    else:
        data = request.GET
    room = rooms.select_related("year").filter(pk=uid(data.get("classroom"))).first()
    if room is None:
        return JsonResponse({"error": "Groupe introuvable."}, status=404)
    try:
        day = date.fromisoformat(data.get("day", ""))
        if day.isoformat() != data["day"]:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"error": "Date invalide."}, status=422)

    if not room.year.start_date <= day <= room.year.end_date or day > timezone.localdate():
        return JsonResponse({"error": "Choisissez une date écoulée dans l’année scolaire."}, status=422)

    roster = Enrollment.objects.filter(
        school=school, student__school=school, classroom=room, year=room.year,
        active=True, student__active=True, enrolled_on__lte=day,
    )
    notes = PreschoolObservation.objects.filter(classroom=room, day=day)
    if request.method == "GET":
        entries = {
            note.enrollment_id: note for note in notes.filter(
                enrollment__school=school, enrollment__year=room.year, enrollment__student__school=school,
            ).select_related("enrollment__student")
        }
        current = {row.pk: row for row in roster.select_related("student")}
        rows = {pk: note.enrollment for pk, note in entries.items()}
        rows.update(current)
        students = []
        for row in sorted(rows.values(), key=lambda row: (row.student.last_name, row.student.first_name, row.pk)):
            entry = entries.get(row.pk)
            students.append({
                "enrollment": str(row.pk), "name": f"{row.student.last_name} {row.student.first_name}",
                "observation": entry.observation if entry else "", "revision": entry.revision if entry else 0,
                "current": row.pk in current,
            })
        editable = room.year.active and room.year.status != AcademicYear.STATUS_CLOSED
        return JsonResponse({"students": students, "editable": editable})

    revision, observation = data["revision"], data["observation"]
    if type(revision) is not int or revision < 0 or not isinstance(observation, str) or not 1 <= len(observation.strip()) <= 600:
        return JsonResponse({"error": "Une observation de 1 à 600 caractères est requise."}, status=422)
    with transaction.atomic():
        year = AcademicYear.objects.select_for_update().get(pk=room.year_id, school=school)
        if not year.active or year.status == AcademicYear.STATUS_CLOSED:
            return JsonResponse({"error": "L’année scolaire est clôturée."}, status=409)
        if not year.start_date <= day <= year.end_date:
            return JsonResponse({"error": "Date hors de l’année scolaire."}, status=422)
        enrollment = roster.select_for_update(of=("self",)).filter(pk=uid(data["enrollment"])).first()
        if enrollment is None:
            return JsonResponse({"error": "Inscription introuvable dans ce groupe."}, status=404)
        note = notes.filter(enrollment=enrollment).first()
        current = note.revision if note else 0
        if revision != current:
            return JsonResponse({"error": "Conflit de version.", "revision": current}, status=409)
        if note is None:
            note = PreschoolObservation(classroom=room, enrollment=enrollment, day=day)
        note.observation = observation.strip()
        note.author = request.user
        note.revision = current + 1
        note.save()
        log_event(school, request, "preschool_observation_saved", str(note.pk), {"revision": note.revision})
    return JsonResponse({"observation": note.observation, "revision": note.revision}, status=200 if current else 201)
