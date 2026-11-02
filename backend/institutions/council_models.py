"""Council decisions and append-only published-report rectifications."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import School
from .academic_models import AcademicYear, AcademicClass, AcademicPeriod
from .student_models import Enrollment
from .report_models import SchoolReport


class SchoolCouncil(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="councils")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="councils")
    classroom = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="councils")
    period = models.ForeignKey(AcademicPeriod, null=True, blank=True, on_delete=models.PROTECT, related_name="councils")
    period_key = models.CharField(max_length=36, blank=True)
    title = models.CharField(max_length=140)
    meeting_date = models.DateField()
    status = models.CharField(max_length=12, default="draft")
    revision = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "classroom", "period_key"], name="unique_school_council_class_period")
        ]

    def clean(self):
        if self.status not in {"draft", "closed"}:
            raise ValidationError("Statut du conseil invalide.")
        if self.school_id and self.year_id and self.year.school_id != self.school_id:
            raise ValidationError("Année d'un autre établissement.")
        if self.classroom_id and (self.classroom.school_id != self.school_id or self.classroom.year_id != self.year_id):
            raise ValidationError("Classe d'une autre école ou année.")
        if self.period_id and (self.period.school_id != self.school_id or self.period.year_id != self.year_id):
            raise ValidationError("Période d'une autre école ou année.")
        if self.period_key != (str(self.period_id) if self.period_id else ""):
            raise ValidationError("Identifiant de période invalide.")


class CouncilDecision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="council_decisions")
    council = models.ForeignKey(SchoolCouncil, on_delete=models.PROTECT, related_name="decisions")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="council_decisions")
    report = models.ForeignKey(SchoolReport, on_delete=models.PROTECT, related_name="council_decisions")
    code = models.SlugField(max_length=48)
    label = models.CharField(max_length=120)
    rationale = models.TextField(max_length=1000)
    revision = models.PositiveIntegerField(default=1)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["council", "enrollment"], name="unique_council_enrollment_decision")]

    def clean(self):
        if self.council_id and self.school_id and self.council.school_id != self.school_id:
            raise ValidationError("Conseil d'une autre école.")
        if self.enrollment_id and self.council_id and (
            self.enrollment.school_id != self.school_id
            or self.enrollment.year_id != self.council.year_id
            or self.enrollment.classroom_id != self.council.classroom_id
        ):
            raise ValidationError("Inscription hors de cette classe et année.")
        if self.report_id and self.enrollment_id and (
            self.report.school_id != self.school_id
            or self.report.enrollment_id != self.enrollment_id
            or self.report.status != "published"
            or self.report.period_id != self.council.period_id
        ):
            raise ValidationError("La décision exige un bulletin publié correspondant à la période.")


class ReportAmendment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="report_amendments")
    report = models.ForeignKey(SchoolReport, on_delete=models.PROTECT, related_name="amendments")
    sequence = models.PositiveIntegerField()
    course_id = models.UUIDField()
    previous_percent = models.CharField(max_length=32, blank=True)
    corrected_percent = models.CharField(max_length=32)
    reason = models.TextField(max_length=1000)
    prior_snapshot = models.JSONField()
    snapshot = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["report", "sequence"], name="unique_report_amendment_sequence")]
        ordering = ["sequence"]

    def clean(self):
        if self.report_id and (self.report.school_id != self.school_id or self.report.status != "published"):
            raise ValidationError("Rectification réservée à un bulletin publié de la même école.")
