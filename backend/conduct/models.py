"""Communications nominatives publiées par la vie scolaire."""
import uuid

from django.conf import settings
from django.db import models


class ConductNotice(models.Model):
    """A message published to the verified family of one enrolled student."""

    class Kind(models.TextChoices):
        OBSERVATION = "observation", "Observation de comportement"
        SANCTION = "sanction", "Sanction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey("institutions.Enrollment", on_delete=models.PROTECT, related_name="conduct_notices")
    date = models.DateField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    message = models.CharField(max_length=500)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    published_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
