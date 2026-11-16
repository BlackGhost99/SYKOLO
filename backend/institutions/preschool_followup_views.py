"""Daily preschool follow-up, scoped to the school and the educator's group."""
from collections import defaultdict
from datetime import date

from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from accounts.views import authorized

from .academic_models import AcademicClass, AcademicYear
from .calendar_views import uid
from .cycle_scope import calendar_assignments, scoped_cycle_ids
from .parent_views import child_scope
from .preschool_followup_models import (
    PreschoolCompetency, PreschoolCompetencyMark, PreschoolLiaisonMessage, PreschoolObservation,
)
from .services import has_permission
from .student_models import Enrollment
from .views import access, log_event, parse_body, refuse, string


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
        school=school, level__school=school, level__cycle__school=school, level__cycle__code="prescolaire",
        year__school=school, active=True,
    )
    allowed = scoped_cycle_ids(request.user, school)
    if allowed is not None:
        rooms = rooms.filter(level__cycle_id__in=allowed)
    can_manage = has_permission(request.user, school, "school.academic.manage")
    if not can_manage:
        rooms = rooms.filter(pk__in=calendar_assignments(request.user, school).filter(duty="enseignant").values("classroom_id"))

    if request.method == "GET" and "classroom" not in request.GET:
        return JsonResponse({"classrooms": list(rooms.filter(
            year_id=uid(request.GET.get("year")),
        ).order_by("name", "pk").values("id", "name"))})

    if request.method == "POST":
        data, error = parse_body(request)
        if error is not None:
            return error
        action = data.pop("action", "observation")
        fields = {
            "observation": {"enrollment", "revision", "observation"},
            "reference": {"label"},
            "mark": {"enrollment", "competency", "stage", "revision"},
            "liaison": {"enrollment", "message"},
        }
        if not isinstance(action, str) or action not in fields or set(data) != fields[action] | {"classroom", "day"}:
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
    competencies = PreschoolCompetency.objects.filter(level_id=room.level_id).order_by("label", "pk")
    marks = PreschoolCompetencyMark.objects.filter(classroom=room, day=day, competency__in=competencies)
    liaison = PreschoolLiaisonMessage.objects.filter(classroom=room, day=day)
    if request.method == "GET":
        entries = {
            note.enrollment_id: note for note in notes.filter(
                enrollment__school=school, enrollment__year=room.year, enrollment__student__school=school,
            ).select_related("enrollment__student")
        }
        current = {row.pk: row for row in roster.select_related("student")}
        rows = {pk: note.enrollment for pk, note in entries.items()}
        marks_by_enrollment = defaultdict(list)
        messages_by_enrollment = defaultdict(list)
        scoped = {"enrollment__school": school, "enrollment__year": room.year,
                  "enrollment__student__school": school}
        for mark in marks.filter(**scoped).select_related("enrollment__student"):
            rows[mark.enrollment_id] = mark.enrollment
            marks_by_enrollment[mark.enrollment_id].append({
                "competency": str(mark.competency_id), "stage": mark.stage, "revision": mark.revision,
            })
        for message in liaison.filter(**scoped).select_related("enrollment__student").order_by("published_at"):
            rows[message.enrollment_id] = message.enrollment
            messages_by_enrollment[message.enrollment_id].append(liaison_output(message))
        rows.update(current)
        students = []
        for row in sorted(rows.values(), key=lambda row: (row.student.last_name, row.student.first_name, row.pk)):
            entry = entries.get(row.pk)
            students.append({
                "enrollment": str(row.pk), "name": f"{row.student.last_name} {row.student.first_name}",
                "observation": entry.observation if entry else "", "revision": entry.revision if entry else 0,
                "current": row.pk in current,
                "marks": marks_by_enrollment[row.pk], "liaison": messages_by_enrollment[row.pk],
            })
        editable = room.year.active and room.year.status != AcademicYear.STATUS_CLOSED
        return JsonResponse({
            "students": students, "editable": editable, "can_manage_reference": can_manage and editable,
            "competencies": list(competencies.values("id", "label")), "stages": PreschoolCompetencyMark.STAGES,
        })

    if action == "reference" and not can_manage:
        return refuse()
    if action == "reference" and not string(data["label"], 120):
        return JsonResponse({"error": "Libellé de compétence invalide."}, status=422)
    if action == "liaison" and not string(data["message"], 600):
        return JsonResponse({"error": "Message de liaison invalide."}, status=422)
    if action in {"mark", "observation"} and (type(data["revision"]) is not int or data["revision"] < 0):
        return JsonResponse({"error": "Révision invalide."}, status=422)
    if action == "mark" and (
        not isinstance(data["stage"], str) or data["stage"] not in PreschoolCompetencyMark.STAGES
    ):
        return JsonResponse({"error": "Niveau de maîtrise invalide."}, status=422)
    if action == "observation" and not string(data["observation"], 600):
        return JsonResponse({"error": "Une observation de 1 à 600 caractères est requise."}, status=422)
    with transaction.atomic():
        year = AcademicYear.objects.select_for_update().get(pk=room.year_id, school=school)
        if not year.active or year.status == AcademicYear.STATUS_CLOSED:
            return JsonResponse({"error": "L’année scolaire est clôturée."}, status=409)
        if not year.start_date <= day <= year.end_date:
            return JsonResponse({"error": "Date hors de l’année scolaire."}, status=422)
        if action == "reference":
            competency, created = PreschoolCompetency.objects.get_or_create(
                level_id=room.level_id, label=data["label"].strip(),
            )
            if created:
                log_event(school, request, "preschool_competency_created", str(competency.pk))
            return JsonResponse({"id": str(competency.pk), "label": competency.label}, status=201 if created else 200)
        enrollment = roster.select_for_update(of=("self",)).filter(pk=uid(data["enrollment"])).first()
        if enrollment is None:
            return JsonResponse({"error": "Inscription introuvable dans ce groupe."}, status=404)
        if action == "liaison":
            entry, created = liaison.get_or_create(
                enrollment=enrollment, classroom=room, day=day, message=data["message"].strip(),
                defaults={"published_by": request.user},
            )
            if created:
                log_event(school, request, "preschool_liaison_published", str(entry.pk))
            return JsonResponse(liaison_output(entry), status=201 if created else 200)
        if action == "mark":
            competency = competencies.filter(pk=uid(data["competency"])).first()
            if competency is None:
                return JsonResponse({"error": "Compétence introuvable pour ce niveau."}, status=404)
            mark = marks.filter(enrollment=enrollment, competency=competency).first()
            current = mark.revision if mark else 0
            if data["revision"] != current:
                return JsonResponse({"error": "Conflit de version.", "revision": current}, status=409)
            if mark is None:
                mark = PreschoolCompetencyMark(classroom=room, enrollment=enrollment, day=day, competency=competency)
            mark.stage = data["stage"]
            mark.revision = current + 1
            mark.save()
            log_event(school, request, "preschool_competency_mark_saved", str(mark.pk), {"revision": mark.revision})
            return JsonResponse({"competency": str(competency.pk), "stage": mark.stage, "revision": mark.revision},
                                status=200 if current else 201)
        note = notes.filter(enrollment=enrollment).first()
        current = note.revision if note else 0
        if data["revision"] != current:
            return JsonResponse({"error": "Conflit de version.", "revision": current}, status=409)
        if note is None:
            note = PreschoolObservation(classroom=room, enrollment=enrollment, day=day)
        note.observation = data["observation"].strip()
        note.author = request.user
        note.revision = current + 1
        note.save()
        log_event(school, request, "preschool_observation_saved", str(note.pk), {"revision": note.revision})
    return JsonResponse({"observation": note.observation, "revision": note.revision}, status=200 if current else 201)


def liaison_output(message):
    return {"id": str(message.pk), "day": message.day.isoformat(), "message": message.message,
            "published_at": message.published_at.isoformat()}


@never_cache
@require_GET
@authorized
def child_liaison(request, student_id):
    student, year_id, error = child_scope(request, student_id)
    if error is not None:
        return error
    entries = PreschoolLiaisonMessage.objects.filter(
        enrollment__student=student, enrollment__school_id=student.school_id,
        classroom__school_id=student.school_id, classroom__level__cycle__code="prescolaire",
        classroom__year_id=F("enrollment__year_id"),
    )
    if year_id:
        entries = entries.filter(enrollment__year_id=year_id, classroom__year_id=year_id)
    try:
        page = int(request.GET.get("page", "1"))
        if not 1 <= page <= 1000:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"error": "Page invalide."}, status=422)
    offset = (page - 1) * 50
    messages = list(entries.order_by("-published_at", "pk")[offset:offset + 51])
    return JsonResponse({
        "messages": [liaison_output(entry) for entry in messages[:50]],
        "has_more": len(messages) > 50,
    })
