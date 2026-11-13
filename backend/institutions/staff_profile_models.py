"""Teacher-owned display profile, attached to the canonical StaffRecord for the school."""
from django.db import models


class StaffProfile(models.Model):
    staff = models.OneToOneField(
        "institutions.StaffRecord", on_delete=models.CASCADE,
        related_name="mobile_profile", primary_key=True,
    )
    presentation = models.CharField(max_length=280, blank=True, default="")
    photo_data = models.BinaryField(null=True, blank=True)
    photo_content_type = models.CharField(max_length=30, blank=True, default="")
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
