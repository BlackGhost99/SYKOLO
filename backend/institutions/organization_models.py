"""Nomination du personnel dans les organigrammes scolaires.

Une nomination ne modifie jamais les permissions du compte SchoolMember.
"""
import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .models import School
from .staff_models import StaffRecord
from .school_functions import validate_position


class SchoolAppointment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="appointments")
    staff = models.ForeignKey(StaffRecord, on_delete=models.PROTECT, related_name="appointments")
    function_code = models.SlugField(max_length=48)
    cycle_code = models.CharField(max_length=32, default="", blank=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    appointed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("school", "staff", "function_code", "cycle_code"),
                name="unique_school_function_appointment",
            ),
        ]
        ordering = ("function_code", "cycle_code", "staff__last_name", "pk")

    @property
    def is_effective(self):
        today = date.today()
        if not (self.active and self.staff.active and
                (self.starts_on is None or self.starts_on <= today) and
                (self.ends_on is None or today <= self.ends_on)):
            return False
        try:
            validate_position(self.school, self.function_code, self.cycle_code)
        except ValueError:
            # A reclassification must not delete old nominations, but invalid
            # functions must stop appearing as currently exercisable.
            return False
        return True

    def clean(self):
        if self.school_id and self.staff_id and self.staff.school_id != self.school_id:
            raise ValidationError("Personnel d'un autre établissement.")
        if self.active and self.staff_id and not self.staff.active:
            raise ValidationError("Impossible de nommer un personnel archivé.")
        if self.starts_on and self.ends_on and self.starts_on > self.ends_on:
            raise ValidationError("La fin de fonction précède son début.")
        if self.school_id:
            try:
                validate_position(self.school, self.function_code, self.cycle_code)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
