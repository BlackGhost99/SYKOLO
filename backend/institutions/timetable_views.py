"""Module 13: weekly schedules with serialized collision checks per establishment."""
import re
from datetime import date, time, timedelta
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import AcademicYear
from .curriculum_models import CourseOffering, CourseInstructor
from .models import School
from .services import has_permission
from .timetable_models import TimetableRoom, TimetableSlot, TimetableEntry
from .views import access, refuse, parse_body, log_event

CODE = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
CLOCK = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def uid(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def day(value):
    try:
        if type(value) is not str:
            raise ValueError
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError:
        raise ValueError("Date ISO invalide.") from None


def clock(value):
    if type(value) is not str or not CLOCK.fullmatch(value):
        raise ValueError("Heure invalide (HH:MM).")
    return time.fromisoformat(value)


def code(value):
    if type(value) is not str or not CODE.fullmatch(value):
        raise ValueError("Code invalide.")
    return value


def title(value):
    if type(value) is not str or not 1 <= len(value.strip()) <= 120:
        raise ValueError("Nom ou libellé invalide.")
    return value.strip()


def active(value):
    if type(value) is not bool:
        raise ValueError("Statut invalide.")
    return value


def weekday(value):
    if type(value) is not int or not 0 <= value <= 6:
        raise ValueError("Jour de semaine invalide (0 lundi à 6 dimanche).")
    return value


def positive_capacity(value):
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= 100000:
        raise ValueError("Capacité invalide.")
    return value


def model_error(error):
    if hasattr(error, "message_dict"):
        return fail(" ".join(t for group in error.message_dict.values() for t in group)[:600])
    return fail(" ".join(error.messages)[:600])


def gate(request, school_id, write=False):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    perm = "school.timetable.manage" if write else "school.timetable.read"
    if not has_permission(request.user, school, perm):
        return None, refuse()
    return school, None


def can_see_class(request, school, classroom_id):
    if has_permission(request.user, school, "school.timetable.manage"):
        return True
    return CourseInstructor.objects.filter(
        school=school, course__classroom_id=classroom_id, active=True,
        staff_assignment__active=True, staff_assignment__staff__active=True,
        staff_assignment__staff__account=request.user
    ).exists()


def room_data(room):
    return {"id": str(room.pk), "code": room.code, "name": room.name,
            "capacity": room.capacity, "active": room.active, "revision": room.revision}


def slot_data(slot):
    return {"id": str(slot.pk), "year": str(slot.year_id), "code": slot.code,
            "label": slot.label, "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "active": slot.active, "revision": slot.revision}


def entry_data(entry):
    staff = entry.instructor.staff_assignment.staff
    return {
        "id": str(entry.pk), "year": str(entry.year_id),
        "classroom": str(entry.classroom_id), "course": str(entry.course_id),
        "subject": entry.course.subject.name, "instructor": str(entry.instructor_id),
        "staff": str(staff.pk), "teacher": f"{staff.first_name} {staff.last_name}",
        "slot": str(entry.slot_id), "room": str(entry.room_id) if entry.room_id else None,
        "weekday": entry.weekday, "effective_from": entry.effective_from.isoformat(),
        "effective_to": entry.effective_to.isoformat(), "active": entry.active, "revision": entry.revision,
        "start_time": entry.slot.start_time.strftime("%H:%M"),
        "end_time": entry.slot.end_time.strftime("%H:%M"),
    }


def payload(request):
    data, error = parse_body(request)
    if error is not None:
        return None, error
    return data, None


def fields(data, mapping, required=(), editing=False):
    if not set(data) <= set(mapping) | ({"revision"} if editing else set()):
        raise ValueError("Champs non autorisés.")
    if not editing and not set(required) <= set(data):
        raise ValueError("Champs obligatoires manquants.")
    if editing and (type(data.get("revision")) is not int or data["revision"] < 1 or len(data) <= 1):
        raise ValueError("Révision invalide.")
    parsed = {}
    for k, v in data.items():
        if k == "revision":
            continue
        parsed[mapping[k][0]] = mapping[k][1](v)
    return parsed


ROOM_FIELDS = {
    "code": ("code", code), "name": ("name", title),
    "capacity": ("capacity", positive_capacity), "active": ("active", active),
}
SLOT_FIELDS = {
    "code": ("code", code), "label": ("label", title),
    "year": ("year_id", uid), "start_time": ("start_time", clock),
    "end_time": ("end_time", clock), "active": ("active", active),
}
ENTRY_FIELDS = {
    "course": ("course_id", uid), "instructor": ("instructor_id", uid),
    "slot": ("slot_id", uid), "room": ("room_id", lambda v: uid(v) if v is not None else None),
    "weekday": ("weekday", weekday),
    "effective_from": ("effective_from", day), "effective_to": ("effective_to", day),
    "active": ("active", active),
}


@require_http_methods(["GET", "POST"])
@authorized
def rooms(request, school_id):
    school, error = gate(request, school_id, request.method == "POST")
    if error is not None:
        return error
    if request.method == "GET":
        return JsonResponse({"rooms": [room_data(x) for x in TimetableRoom.objects.filter(
            school=school).order_by("name", "pk")[:250]]})
    data, error = payload(request)
    if error is not None:
        return error
    try:
        values = fields(data, ROOM_FIELDS, ("code", "name"))
        with transaction.atomic():
            row = TimetableRoom(school=school, **values)
            row.full_clean()
            row.save()
            log_event(school, request, "timetable_room_created", row.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return fail("Code de salle déjà enregistré.", 409)
    return JsonResponse(room_data(row), status=201)


@require_http_methods(["GET", "PATCH"])
@authorized
def room_detail(request, school_id, room_id):
    school, error = gate(request, school_id, request.method == "PATCH")
    if error is not None:
        return error
    row = TimetableRoom.objects.filter(school=school, pk=room_id).first()
    if row is None:
        return fail("Salle introuvable.", 404)
    if request.method == "GET":
        return JsonResponse(room_data(row))
    data, error = payload(request)
    if error is not None:
        return error
    try:
        values = fields(data, {k: v for k, v in ROOM_FIELDS.items() if k != "code"}, editing=True)
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            row = TimetableRoom.objects.select_for_update().get(pk=room_id, school=school)
            if row.revision != data["revision"]:
                return fail("Conflit de version.", 409)
            if values.get("active") is False and TimetableEntry.objects.filter(room=row, school=school, active=True).exists():
                return fail("Une salle planifiée ne peut être désactivée.", 409)
            for k, v in values.items():
                setattr(row, k, v)
            row.full_clean()
            row.revision += 1
            row.save()
            log_event(school, request, "timetable_room_changed", row.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return model_error(exc)
    return JsonResponse(room_data(row))


@require_http_methods(["GET", "POST"])
@authorized
def slots(request, school_id):
    school, error = gate(request, school_id, request.method == "POST")
    if error is not None:
        return error
    if request.method == "GET":
        rows = TimetableSlot.objects.filter(school=school)
        if "year" in request.GET:
            year = uid(request.GET.get("year"))
            if year is None:
                return fail("Année invalide.")
            rows = rows.filter(year_id=year)
        return JsonResponse({"slots": [slot_data(x) for x in rows.order_by("start_time", "pk")[:250]]})
    data, error = payload(request)
    if error is not None:
        return error
    try:
        values = fields(data, SLOT_FIELDS, ("code", "label", "year", "start_time", "end_time"))
        if not values["year_id"] or not AcademicYear.objects.filter(school=school, pk=values["year_id"], active=True).exists():
            return fail("Année scolaire inconnue.")
        with transaction.atomic():
            row = TimetableSlot(school=school, **values)
            row.full_clean()
            row.save()
            log_event(school, request, "timetable_slot_created", row.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return fail("Créneau existant.", 409)
    return JsonResponse(slot_data(row), status=201)


@require_http_methods(["GET", "PATCH"])
@authorized
def slot_detail(request, school_id, slot_id):
    school, error = gate(request, school_id, request.method == "PATCH")
    if error is not None:
        return error
    row = TimetableSlot.objects.filter(school=school, pk=slot_id).first()
    if row is None:
        return fail("Créneau introuvable.", 404)
    if request.method == "GET":
        return JsonResponse(slot_data(row))
    data, error = payload(request)
    if error is not None:
        return error
    try:
        values = fields(data, {k: v for k, v in SLOT_FIELDS.items() if k not in ("code", "year")}, editing=True)
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            row = TimetableSlot.objects.select_for_update().get(pk=slot_id, school=school)
            if row.revision != data["revision"]:
                return fail("Conflit de version.", 409)
            if TimetableEntry.objects.filter(slot=row, school=school, active=True).exists() and (
                "start_time" in values or "end_time" in values or values.get("active") is False
            ):
                return fail("Déplacez ou archivez les séances avant de modifier cet horaire.", 409)
            for k, v in values.items():
                setattr(row, k, v)
            row.full_clean()
            row.revision += 1
            row.save()
            log_event(school, request, "timetable_slot_changed", row.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return model_error(exc)
    return JsonResponse(slot_data(row))


def overlaps_date_weekday(a, b, weekday_number):
    start = max(a.effective_from, b.effective_from)
    end = min(a.effective_to, b.effective_to)
    if start > end:
        return False
    offset = (weekday_number - start.weekday()) % 7
    return start + timedelta(days=offset) <= end


def collisions(school, entry):
    if not entry.active:
        return []
    rows = TimetableEntry.objects.select_related(
        "slot", "instructor__staff_assignment", "course__subject"
    ).filter(school=school, year=entry.year, weekday=entry.weekday, active=True,
             effective_from__lte=entry.effective_to, effective_to__gte=entry.effective_from).exclude(pk=entry.pk)
    errors = []
    teacher_id = entry.instructor.staff_assignment.staff_id
    for other in rows:
        if not (entry.slot.start_time < other.slot.end_time and other.slot.start_time < entry.slot.end_time):
            continue
        if not overlaps_date_weekday(entry, other, entry.weekday):
            continue
        resources = []
        if entry.classroom_id == other.classroom_id:
            resources.append("classe")
        if entry.room_id is not None and entry.room_id == other.room_id:
            resources.append("salle")
        if teacher_id == other.instructor.staff_assignment.staff_id:
            resources.append("enseignant")
        if resources:
            errors.append({"entry": str(other.pk), "resources": resources,
                           "weekday": entry.weekday,
                           "start": other.slot.start_time.strftime("%H:%M"),
                           "end": other.slot.end_time.strftime("%H:%M")})
    return errors


def entry_object(school, values, current=None):
    if current is None:
        course = CourseOffering.objects.select_related("year", "classroom").filter(
            school=school, pk=values.get("course_id"), active=True
        ).first()
        if course is None:
            raise ValueError("Cours actif introuvable dans cette école.")
        entry = TimetableEntry(school=school, year=course.year, classroom=course.classroom, course=course)
    else:
        entry = current
    for k, v in values.items():
        setattr(entry, k, v)
    if not entry.instructor_id or not entry.slot_id:
        raise ValueError("Enseignant et créneau obligatoires.")
    try:
        entry.full_clean()
    except ValidationError:
        raise
    return entry


def visible_entries(request, school):
    entries = TimetableEntry.objects.select_related(
        "slot", "room", "course__subject", "instructor__staff_assignment__staff"
    ).filter(school=school)
    if not has_permission(request.user, school, "school.timetable.manage"):
        entries = entries.filter(instructor__staff_assignment__staff__account=request.user)
    return entries


@require_http_methods(["GET", "POST"])
@authorized
def entries(request, school_id):
    school, error = gate(request, school_id, request.method == "POST")
    if error is not None:
        return error
    if request.method == "GET":
        rows = visible_entries(request, school)
        if "year" in request.GET:
            uid_year = uid(request.GET.get("year"))
            if uid_year is None:
                return fail("Année invalide.")
            rows = rows.filter(year_id=uid_year)
        if "classroom" in request.GET:
            uid_class = uid(request.GET.get("classroom"))
            if uid_class is None:
                return fail("Classe invalide.")
            if not can_see_class(request, school, uid_class):
                return refuse()
            rows = rows.filter(classroom_id=uid_class)
        return JsonResponse({"entries": [entry_data(x) for x in rows.order_by(
            "weekday", "slot__start_time", "pk")[:500]]})
    data, error = payload(request)
    if error is not None:
        return error
    try:
        values = fields(data, ENTRY_FIELDS, (
            "course", "instructor", "slot", "weekday", "effective_from", "effective_to"
        ))
        if any(values.get(k) is None for k in ("course_id", "instructor_id", "slot_id")):
            raise ValueError("Cours, enseignant et créneau obligatoires.")
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            entry = entry_object(school, values)
            conflicts = collisions(school, entry)
            if conflicts:
                return JsonResponse({"error": "Conflit d'horaires.", "conflicts": conflicts}, status=409)
            entry.created_by = request.user
            entry.save()
            log_event(school, request, "timetable_entry_created", entry.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return model_error(exc)
    return JsonResponse(entry_data(TimetableEntry.objects.select_related(
        "slot", "room", "course__subject", "instructor__staff_assignment__staff"
    ).get(pk=entry.pk)), status=201)


@require_http_methods(["GET", "PATCH"])
@authorized
def entry_detail(request, school_id, entry_id):
    school, error = gate(request, school_id, request.method == "PATCH")
    if error is not None:
        return error
    current = visible_entries(request, school).filter(pk=entry_id).first()
    if current is None:
        return fail("Séance introuvable.", 404)
    if request.method == "GET":
        return JsonResponse(entry_data(current))
    data, error = payload(request)
    if error is not None:
        return error
    try:
        values = fields(data, {k: v for k, v in ENTRY_FIELDS.items() if k != "course"}, editing=True)
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            current = TimetableEntry.objects.select_for_update().get(pk=entry_id, school=school)
            if current.revision != data["revision"]:
                return JsonResponse({"error": "Conflit de version.", "revision": current.revision}, status=409)
            current = entry_object(school, values, current=current)
            conflicts = collisions(school, current)
            if conflicts:
                return JsonResponse({"error": "Conflit d'horaires.", "conflicts": conflicts}, status=409)
            current.revision += 1
            current.save()
            log_event(school, request, "timetable_entry_changed", current.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return model_error(exc)
    current = TimetableEntry.objects.select_related(
        "slot", "room", "course__subject", "instructor__staff_assignment__staff"
    ).get(pk=current.pk)
    return JsonResponse(entry_data(current))
