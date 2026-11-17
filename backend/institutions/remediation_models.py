"""Individual secondary-school competency follow-up per curriculum unit."""
from django.conf import settings
from django.db import models
from .curriculum_models import CourseUnit
from .student_models import Enrollment


class SecondaryMastery(models.Model):
    unit = models.ForeignKey(CourseUnit, on_delete=models.PROTECT)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT)
    stage = models.CharField(max_length=16, choices=[
        ("not_yet", "À travailler"), ("developing", "En cours"), ("achieved", "Acquis"),
    ])
    action = models.CharField(max_length=500, blank=True)
    action_status = models.CharField(max_length=16, choices=[
        ("", "Aucune action"), ("planned", "À engager"), ("ongoing", "En cours"), ("completed", "Réalisée"),
    ], blank=True)
    due_on = models.DateField(null=True, blank=True)
    unit_title = models.CharField(max_length=180)
    objectives_snapshot = models.TextField(max_length=2000, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["unit","enrollment"], name="yem_secondary_mastery_unique"),
            models.CheckConstraint(condition=models.Q(stage__in=["not_yet","developing","achieved"]), name="yem_secondary_stage_valid"),
            models.CheckConstraint(condition=models.Q(action_status__in=["planned","ongoing","completed"]) | models.Q(action_status="", action="", due_on__isnull=True), name="yem_secondary_action_valid"),
        ]
