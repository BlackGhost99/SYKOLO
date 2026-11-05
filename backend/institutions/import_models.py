"""Minimal metadata for audited, repeatable student imports (never store uploaded files)."""
import uuid
from django.conf import settings
from django.db import models
from .models import School


class StudentImportProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="student_import_profiles")
    name = models.CharField(max_length=80)
    headers = models.JSONField(default=list)
    mapping = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "name"], name="unique_school_import_profile")]


class StudentImportBatch(models.Model):
    """The fingerprint prevents re-importing a committed file/mapping for one school."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="student_import_batches")
    fingerprint = models.CharField(max_length=64)
    row_count = models.PositiveIntegerField()
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "fingerprint"], name="unique_school_import_fingerprint")]
