"""One progress record per existing curriculum unit."""
from django.conf import settings
from django.db import models
from .curriculum_models import CourseUnit
from .teaching_diary_models import TeachingDiaryEntry


class CourseUnitProgress(models.Model):
    unit = models.OneToOneField(CourseUnit, primary_key=True, on_delete=models.PROTECT, related_name="progress")
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=[
        ("not_started", "Non commencé"), ("in_progress", "En cours"), ("completed", "Dispensé")
    ], default="not_started")
    completed_on = models.DateField(null=True, blank=True)
    evidence = models.ForeignKey(TeachingDiaryEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="unit_progress")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(planned_start__isnull=True) | models.Q(planned_end__isnull=True) | models.Q(planned_end__gte=models.F("planned_start")), name="yem_progress_plan_dates"),
            models.CheckConstraint(condition=models.Q(status="completed", completed_on__isnull=False) | models.Q(status__in=["not_started","in_progress"], completed_on__isnull=True), name="yem_progress_completion"),
        ]
