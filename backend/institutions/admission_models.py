"""Admission applications are distinct from official enrollments and personal student records."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import School
from .academic_models import AcademicYear, AcademicClass
from .student_models import Student, Enrollment

ROUTES = (("direct", "Inscription directe"), ("concours", "Concours ou test"),
          ("orientation", "Affectation ou orientation"))
OUTCOMES = (("pending", "À vérifier"), ("eligible", "Éligible"),
            ("ineligible", "Non éligible"))
DOCUMENT_STATES = (("pending", "À vérifier"), ("verified", "Vérifié"),
                   ("rejected", "Non conforme"))

APPLICATION_STATES = (
    ("submitted", "Déposée"),
    ("review", "En cours d'étude"),
    ("accepted", "Admise"),
    ("rejected", "Refusée"),
    ("enrolled", "Inscrite"),
)

class AdmissionApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="admission_applications")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="admission_applications")
    classroom = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="admission_applications")
    existing_student = models.ForeignKey(Student, on_delete=models.PROTECT, null=True, blank=True, related_name="admission_applications")
    enrollment = models.OneToOneField(Enrollment, on_delete=models.PROTECT, null=True, blank=True, related_name="admission_application")
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    date_of_birth = models.DateField(null=True, blank=True)
    guardian_name = models.CharField(max_length=180)
    guardian_relationship = models.CharField(max_length=80, blank=True)
    guardian_phone = models.CharField(max_length=45, blank=True)
    guardian_email = models.EmailField(blank=True)
    source = models.SlugField(max_length=48)
    route = models.CharField(max_length=16, choices=ROUTES, default="direct")
    origin_school = models.CharField(max_length=180, blank=True)
    route_reference = models.CharField(max_length=140, blank=True)
    orientation_authority = models.CharField(max_length=120, blank=True)
    external_result = models.CharField(max_length=16, choices=OUTCOMES, default="pending")
    required_documents = models.JSONField(default=list, blank=True)
    # Fixed at application intake or acceptance; avoids re-pricing old admissions.
    admission_fee_snapshot_xaf = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=APPLICATION_STATES, default="submitted")
    decision_reason = models.CharField(max_length=1000, blank=True)
    revision = models.PositiveIntegerField(default=1)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "year", "classroom", "status"], name="admission_workflow_idx"),
        ]

    def clean(self):
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("Année d'un autre établissement.")
        if self.classroom_id and self.school_id and (
            self.classroom.school_id != self.school_id or self.classroom.year_id != self.year_id
        ):
            raise ValidationError("Classe ou année incohérentes.")
        if self.existing_student_id and self.school_id and self.existing_student.school_id != self.school_id:
            raise ValidationError("Élève existant dans un autre établissement.")
        if self.enrollment_id and self.school_id and (
            self.enrollment.school_id != self.school_id or
            self.enrollment.year_id != self.year_id or
            self.enrollment.classroom_id != self.classroom_id
        ):
            raise ValidationError("Inscription officielle étrangère ou incohérente.")


class AdmissionEvent(models.Model):
    """Append-only workflow evidence; no API endpoint alters or deletes events."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="admission_events")
    application = models.ForeignKey(AdmissionApplication, on_delete=models.PROTECT, related_name="events")
    previous_status = models.CharField(max_length=16, blank=True)
    new_status = models.CharField(max_length=16)
    reason = models.CharField(max_length=1000, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "id"]

    def clean(self):
        if self.school_id and self.application_id and self.application.school_id != self.school_id:
            raise ValidationError("Événement rattaché à un autre établissement.")


class AdmissionPolicy(models.Model):
    """Rules for an academic year, optionally refined per level.

    Requirements are document codes, not files or national credentials.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="admission_policies")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="admission_policies")
    level = models.ForeignKey("institutions.AcademicLevel", on_delete=models.PROTECT,
                              null=True, blank=True, related_name="admission_policies")
    scope_key = models.CharField(max_length=85)
    enabled_routes = models.JSONField(default=list)
    required_documents = models.JSONField(default=dict, blank=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "scope_key"], name="unique_school_admission_policy_scope"),
        ]

    def clean(self):
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("L'année doit appartenir à cet établissement.")
        if self.level_id and self.school_id and self.level.school_id != self.school_id:
            raise ValidationError("Le niveau doit appartenir à cet établissement.")


class AdmissionDocument(models.Model):
    """Reviewed document references only; no unprotected child files or scans."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="admission_documents")
    application = models.ForeignKey(AdmissionApplication, on_delete=models.PROTECT, related_name="documents")
    code = models.SlugField(max_length=48)
    reference = models.CharField(max_length=180)
    status = models.CharField(max_length=16, choices=DOCUMENT_STATES, default="pending")
    review_reason = models.CharField(max_length=280, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["application", "code"], name="unique_admission_document_code"),
        ]

    def clean(self):
        if self.school_id and self.application_id and self.application.school_id != self.school_id:
            raise ValidationError("La pièce justificative appartient à un autre établissement.")
