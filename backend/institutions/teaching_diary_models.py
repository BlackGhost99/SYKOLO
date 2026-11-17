"""Class teaching diary; no individual grades or personal student information."""
import uuid

from django.conf import settings
from django.db import models
from .curriculum_models import CourseOffering


class TeachingDiaryEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(CourseOffering, on_delete=models.PROTECT, related_name="diary_entries")
    day = models.DateField()
    title = models.CharField(max_length=180)
    lesson = models.TextField(max_length=4000)
    homework = models.TextField(max_length=4000, blank=True)
    due_on = models.DateField(null=True, blank=True)
    published = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["course", "-day"], name="yem_diary_course_day_idx")]
        constraints = [models.CheckConstraint(condition=models.Q(due_on__isnull=True) | models.Q(due_on__gte=models.F("day")), name="yem_diary_due_after_day")]
