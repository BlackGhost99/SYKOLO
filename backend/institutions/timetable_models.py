"""Recurring weekly teaching timetable, school-scoped rooms and defined time slots."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from .models import School
from .academic_models import AcademicYear, AcademicClass
from .curriculum_models import CourseOffering, CourseInstructor


class TimetableRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="timetable_rooms")
    code = models.SlugField(max_length=48)
    name = models.CharField(max_length=120)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "code"], name="unique_school_timetable_room")]

    def clean(self):
        if self.capacity is not None and not 1 <= self.capacity <= 100000:
            raise ValidationError("Capacité invalide.")


class TimetableSlot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="timetable_slots")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="timetable_slots")
    code = models.SlugField(max_length=48)
    label = models.CharField(max_length=120)
    start_time = models.TimeField()
    end_time = models.TimeField()
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "year", "code"], name="unique_school_year_slot")]

    def clean(self):
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("Année scolaire étrangère.")
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Le créneau doit finir après son début.")


class TimetableEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="timetable_entries")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="timetable_entries")
    classroom = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="timetable_entries")
    course = models.ForeignKey(CourseOffering, on_delete=models.PROTECT, related_name="timetable_entries")
    instructor = models.ForeignKey(CourseInstructor, on_delete=models.PROTECT, related_name="timetable_entries")
    slot = models.ForeignKey(TimetableSlot, on_delete=models.PROTECT, related_name="entries")
    room = models.ForeignKey(TimetableRoom, on_delete=models.PROTECT, null=True, blank=True, related_name="entries")
    weekday = models.PositiveSmallIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField()
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["school", "year", "weekday", "active"], name="timetable_weekly_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(weekday__gte=0, weekday__lte=6), name="timetable_weekday_bounds"),
            models.CheckConstraint(condition=Q(effective_to__gte=models.F("effective_from")), name="timetable_effective_bounds"),
        ]

    def clean(self):
        if not (0 <= self.weekday <= 6):
            raise ValidationError("Jour invalide (0 lundi à 6 dimanche).")
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("Année scolaire étrangère.")
        if self.classroom_id and (self.classroom.school_id != self.school_id or self.classroom.year_id != self.year_id):
            raise ValidationError("Classe incompatible avec l'année ou l'école.")
        if self.course_id and (self.course.school_id != self.school_id or self.course.year_id != self.year_id
                               or self.course.classroom_id != self.classroom_id):
            raise ValidationError("Cours d'une autre classe ou école.")
        if self.slot_id and (self.slot.school_id != self.school_id or self.slot.year_id != self.year_id):
            raise ValidationError("Créneau d'une autre année ou école.")
        if self.instructor_id and (
            self.instructor.school_id != self.school_id or self.instructor.course_id != self.course_id
            or self.instructor.staff_assignment.school_id != self.school_id
            or self.instructor.staff_assignment.year_id != self.year_id
            or self.instructor.staff_assignment.classroom_id != self.classroom_id
        ):
            raise ValidationError("Enseignant non affecté à ce cours et cette classe.")
        if self.room_id and self.room.school_id != self.school_id:
            raise ValidationError("Salle d'une autre école.")
        if self.effective_from and self.effective_to:
            if self.effective_from > self.effective_to:
                raise ValidationError("Intervalle de dates inversé.")
            if self.year_id and not (
                self.year.start_date <= self.effective_from <= self.effective_to <= self.year.end_date
            ):
                raise ValidationError("Programmation hors de l'année scolaire.")
        if self.active:
            if not all([self.year.active, self.classroom.active, self.course.active,
                        self.slot.active, self.instructor.active,
                        self.instructor.staff_assignment.active,
                        self.instructor.staff_assignment.staff.active]):
                raise ValidationError("Un élément lié à la séance est inactif.")
            if self.room_id and not self.room.active:
                raise ValidationError("Salle inactive.")
