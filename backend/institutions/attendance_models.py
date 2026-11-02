"""Attendance is recorded per class/date/session, never globally across schools."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import School
from .academic_models import AcademicClass
from .student_models import Enrollment


class AttendanceSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="attendance_sessions")
    classroom = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="attendance_sessions")
    attendance_date = models.DateField()
    slot = models.SlugField(max_length=48)
    label = models.CharField(max_length=120)
    revision = models.PositiveIntegerField(default=1)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "classroom", "attendance_date", "slot"],
                                    name="unique_attendance_class_date_slot")
        ]

    def clean(self):
        if self.classroom_id and self.school_id and self.classroom.school_id != self.school_id:
            raise ValidationError("Séance d'un autre établissement.")
        if self.classroom_id and self.attendance_date and not (
            self.classroom.year.start_date <= self.attendance_date <= self.classroom.year.end_date
        ):
            raise ValidationError("Séance hors de l'année scolaire.")


class AttendanceMark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="attendance_marks")
    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name="marks")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="attendance_marks")
    status_code = models.SlugField(max_length=48)
    status_label = models.CharField(max_length=120)
    status_group = models.SlugField(max_length=16)
    note = models.CharField(max_length=500, blank=True)
    justification = models.CharField(max_length=500, blank=True)
    justified = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "session", "enrollment"],
                                    name="unique_attendance_mark_per_session")
        ]

    def clean(self):
        if self.session_id and self.school_id and self.session.school_id != self.school_id:
            raise ValidationError("Séance étrangère à cette école.")
        if self.enrollment_id and self.session_id and (
            self.enrollment.school_id != self.school_id
            or self.enrollment.year_id != self.session.classroom.year_id
            or self.enrollment.classroom_id != self.session.classroom_id
            or self.enrollment.enrolled_on > self.session.attendance_date
        ):
            raise ValidationError("Inscription hors classe ou postérieure à la séance.")
        if self.justified and not self.justification.strip():
            raise ValidationError("Une justification doit accompagner le statut justifié.")


class AttendanceChange(models.Model):
    """Append-only per-mark audit snapshot; there are no update/delete endpoints."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    mark = models.ForeignKey(AttendanceMark, on_delete=models.PROTECT, related_name="changes")
    revision = models.PositiveIntegerField()
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField()
    reason = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["mark", "revision"], name="unique_attendance_mark_change")
        ]
        ordering = ["revision"]

    def clean(self):
        if self.mark_id and self.school_id and self.mark.school_id != self.school_id:
            raise ValidationError("Historique d'une autre école.")
