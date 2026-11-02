"""Personnel scolaire : identité professionnelle et affectations annuelles aux classes."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import School, SchoolMember
from .academic_models import AcademicYear, AcademicClass


class StaffRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="staff_records")
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="staff_records")
    staff_code = models.SlugField(max_length=50)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    position = models.CharField(max_length=100)
    hired_on = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "staff_code"], name="unique_school_staff_code"),
            models.UniqueConstraint(fields=["school", "account"], name="unique_school_staff_account"),
        ]

    def clean(self):
        if self.school_id and self.account_id and not SchoolMember.objects.filter(
            school_id=self.school_id, user_id=self.account_id, active=True
        ).exists():
            raise ValidationError("Ce compte n'est pas membre actif de l'établissement.")


class StaffAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="staff_assignments")
    staff = models.ForeignKey(StaffRecord, on_delete=models.PROTECT, related_name="assignments")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="staff_assignments")
    classroom = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="staff_assignments")
    duty = models.SlugField(max_length=50, default="enseignant")
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "staff", "year", "classroom", "duty"], name="unique_staff_assignment"),
        ]

    def clean(self):
        if self.school_id and self.staff_id and self.staff.school_id != self.school_id:
            raise ValidationError("Personnel d'un autre établissement.")
        if self.school_id and self.year_id and self.year.school_id != self.school_id:
            raise ValidationError("Année d'un autre établissement.")
        if self.classroom_id and self.school_id and (
            self.classroom.school_id != self.school_id or self.classroom.year_id != self.year_id
        ):
            raise ValidationError("Classe et année incohérentes.")
        if self.active and self.staff_id and not self.staff.active:
            raise ValidationError("Impossible d'affecter un membre du personnel archivé.")
