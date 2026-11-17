"""Private, bounded attachments for existing diary entries."""
import uuid
from django.conf import settings
from django.db import models
from .teaching_diary_models import TeachingDiaryEntry


class DiaryResource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(TeachingDiaryEntry, on_delete=models.PROTECT, related_name="resources")
    filename = models.CharField(max_length=160)
    content_type = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    digest = models.CharField(max_length=64)
    data = models.BinaryField()
    active = models.BooleanField(default=True)
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(size__gte=1, size__lte=1048576), name="yem_resource_size_bound"),
        ]
