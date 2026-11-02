"""Explicit, revocable account-to-legal-guardian verification for the parent portal.

Contact data (email/phone) never grants access on its own.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import School
from .student_models import StudentGuardian


class GuardianAccountLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="guardian_account_links")
    guardian = models.ForeignKey(StudentGuardian, on_delete=models.PROTECT, related_name="account_links")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="yem_guardian_links")
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    verified_at = models.DateTimeField(auto_now_add=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "guardian", "user"], name="unique_school_guardian_account"),
        ]

    def clean(self):
        if self.school_id and self.guardian_id and (
            self.guardian.school_id != self.school_id or self.guardian.student.school_id != self.school_id
        ):
            raise ValidationError("Responsable légal d'un autre établissement.")
        if self.active and self.guardian_id and (
            not self.guardian.active or not self.guardian.student.active
        ):
            raise ValidationError("Responsable légal ou élève inactif.")
