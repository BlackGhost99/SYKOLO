import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    created_at = models.DateTimeField(auto_now_add=True)


class OrganizationMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=32, default="founder")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="unique_org_membership")
        ]


class School(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="schools")
    name = models.CharField(max_length=180)
    short_name = models.CharField(max_length=60, blank=True)
    primary_color = models.CharField(max_length=7, default="#1B664C")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SchoolRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="roles")
    code = models.SlugField(max_length=48)
    label = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], name="unique_school_role")
        ]


class SchoolMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.ForeignKey(SchoolRole, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "user"], name="unique_school_membership")
        ]

    def clean(self):
        if self.role_id and self.school_id and self.role.school_id != self.school_id:
            raise ValidationError("Un rôle doit appartenir au même établissement.")


class SchoolSetting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="settings")
    scope_key = models.CharField(max_length=260)
    scope = models.JSONField(default=dict)
    values = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "scope_key"], name="unique_school_setting_scope")
        ]


class SchoolAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    event = models.CharField(max_length=48)
    subject = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


# Django discovers the academic models through the institution app.
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicTrack, AcademicClass, AcademicPeriod  # noqa: E402,F401

from .student_models import Student, StudentGuardian, Enrollment, EnrollmentEvent  # noqa: E402,F401

from .staff_models import StaffRecord, StaffAssignment  # noqa: E402,F401

from .curriculum_models import Subject, CourseOffering, CourseUnit, CourseInstructor  # noqa: E402,F401

from .assessment_models import Assessment, AssessmentGrade  # noqa: E402,F401
