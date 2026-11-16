"""Private, school-scoped messages for staff and verified family workflows."""
import uuid
from django.conf import settings
from django.db import models
from .models import School
from .parent_existing_models import ExistingStudentLinkRequest


class SchoolFamilyNotification(models.Model):
    TO_SCHOOL = "school"
    TO_PARENT = "parent"
    DIRECTION_CHOICES = [(TO_SCHOOL, "Établissement"), (TO_PARENT, "Parent")]
    ORIGIN_CHOICES = [("system", "YEM"), ("school", "Établissement"), ("parent", "Parent")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="family_notifications")
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="yem_school_notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    existing_request = models.ForeignKey(ExistingStudentLinkRequest, on_delete=models.PROTECT, null=True, blank=True, related_name="notification_messages")
    destination = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    origin = models.CharField(max_length=10, choices=ORIGIN_CHOICES)
    student = models.ForeignKey("institutions.Student", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    event_key = models.CharField(max_length=120, blank=True, default="")
    message = models.CharField(max_length=700)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "parent", "event_key"], condition=~models.Q(event_key=""), name="unique_family_notice_event")]
        indexes = [
            models.Index(fields=["school", "destination", "-created_at"], name="yem_family_inbox_school"),
            models.Index(fields=["parent", "destination", "-created_at"], name="yem_family_inbox_parent"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.existing_request_id and (
            self.existing_request.school_id != self.school_id or self.existing_request.owner_id != self.parent_id
        ):
            raise ValidationError("La notification ne correspond pas au dossier de cette famille.")
