"""Individual primary-school mastery recorded against a pedagogical milestone."""
import uuid

from django.db import models


class PrimaryMastery(models.Model):
    STAGES = {"not_yet": "À travailler", "developing": "En cours", "achieved": "Acquis"}
    REMEDIATION = {"planned": "À engager", "ongoing": "En cours", "completed": "Réalisée"}
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey("AcademicClass", on_delete=models.PROTECT)
    milestone = models.ForeignKey("AcademicPeriod", on_delete=models.PROTECT)
    enrollment = models.ForeignKey("Enrollment", on_delete=models.PROTECT)
    criterion_id = models.UUIDField()
    criterion_snapshot = models.JSONField()
    stage = models.CharField(max_length=16, choices=list(STAGES.items()))
    remediation_status = models.CharField(max_length=16, choices=list(REMEDIATION.items()), blank=True)
    follow_up = models.CharField(max_length=500, blank=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "milestone", "enrollment", "criterion_id"],
                name="unique_primary_mastery_per_milestone",
            ),
        ]
