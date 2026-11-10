import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .school_profiles import SCHOOL_TYPE_CHOICES


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
    school_type = models.CharField(max_length=32, choices=SCHOOL_TYPE_CHOICES, default="non_classe")
    education_cycles = models.JSONField(default=list, blank=True)
    enabled_functions = models.JSONField(null=True, default=None, blank=True)
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
    additional_roles = models.ManyToManyField(SchoolRole, blank=True, related_name="additional_members")
    active = models.BooleanField(default=True)
    is_school_owner = models.BooleanField(default=False, db_default=False, editable=False)
    function_codes = models.JSONField(default=list, blank=True)
    # None = legacy / portée générale ; une liste d’UUID = cycles académiques autorisés.
    access_cycle_ids = models.JSONField(null=True, default=None, blank=True)

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


class SchoolAdminPolicy(models.Model):
    """Platform-managed commercial limits; null means unlimited.

    This record is not an invoice or a payment subscription. It is kept separate
    from pedagogical settings so school administrators cannot raise their caps.
    """
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="admin_policy")
    plan_name = models.CharField(max_length=80, default="Sans formule")
    max_users = models.PositiveIntegerField(null=True, blank=True)
    max_students = models.PositiveIntegerField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class PlatformAudit(models.Model):
    """Record high-impact platform actions without storing credentials."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True)
    event = models.CharField(max_length=48, db_index=True)
    subject = models.CharField(max_length=180)
    reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class SchoolAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    event = models.CharField(max_length=48)
    subject = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


# Django discovers the academic models through the institution app.
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicTrack, AcademicClass, AcademicPeriod  # noqa: E402,F401

from .student_models import Student, StudentGuardian, Enrollment, EnrollmentEvent  # noqa: E402,F401

from .staff_models import StaffRecord, StaffAssignment  # noqa: E402,F401

from .curriculum_models import Subject, CourseOffering, CourseUnit, CourseInstructor  # noqa: E402,F401

from .assessment_models import Assessment, AssessmentGrade  # noqa: E402,F401

from .report_models import SchoolReport  # noqa: E402,F401

from .council_models import SchoolCouncil, CouncilDecision, ReportAmendment  # noqa: E402,F401

from .finance_models import FeeSchedule, FeeCharge, FeePayment, FeePaymentVoid  # noqa: E402,F401

from .attendance_models import AttendanceSession, AttendanceMark, AttendanceChange  # noqa: E402,F401

from .timetable_models import TimetableRoom, TimetableSlot, TimetableEntry  # noqa: E402,F401

from .admission_models import AdmissionApplication, AdmissionEvent, AdmissionPolicy, AdmissionDocument  # noqa: E402,F401

from .admission_finance import AdmissionFinancePolicy, GovernmentScholarship  # noqa: E402,F401

from .parent_models import GuardianAccountLink  # noqa: E402,F401
from .parent_admission_models import SchoolPublicListing, FamilyChild, ParentAdmissionRequest  # noqa: E402,F401
from .parent_payment_models import SchoolAdmissionFee, SchoolPaymentGateway, ParentPaymentAttempt, SchoolDemoPaymentConfig, AdmissionCashReceipt, AdmissionCashReceiptVoid  # noqa: E402,F401

from .organization_models import SchoolAppointment  # noqa: E402,F401
from .singpay_models import SingPayMerchant, SingPayIntent, SingPayEvent, SingPaySettlement  # noqa: E402,F401


class SchoolLogin(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    username = models.CharField(max_length=150)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "username"], name="unique_school_login"),
            models.UniqueConstraint(fields=["school", "user"], name="unique_school_login_user"),
        ]


class PermissionDelegation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    member = models.ForeignKey(SchoolMember, on_delete=models.PROTECT, related_name="delegations")
    permissions = models.JSONField(default=list)
    reason = models.CharField(max_length=240)
    source_function = models.CharField(max_length=48, blank=True)
    class_cycle = models.SlugField(max_length=40, blank=True, default="")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    revocation_reason = models.CharField(max_length=240, blank=True)


from .import_models import StudentImportProfile, StudentImportBatch  # noqa: E402,F401
