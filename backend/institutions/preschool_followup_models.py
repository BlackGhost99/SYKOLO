"""Internal daily observations for preschool groups."""
import uuid
from django.conf import settings
from django.db import models


class PreschoolObservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey("AcademicClass", on_delete=models.PROTECT)
    enrollment = models.ForeignKey("Enrollment", on_delete=models.PROTECT)
    day = models.DateField()
    observation = models.CharField(max_length=600)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["enrollment", "day", "classroom"], name="unique_preschool_observation_per_day",
        )]


class PreschoolCompetency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.ForeignKey("AcademicLevel", on_delete=models.PROTECT)
    label = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["level", "label"], name="unique_preschool_competency_label",
        )]


class PreschoolCompetencyMark(models.Model):
    STAGES = {"emerging": "En découverte", "developing": "En cours", "achieved": "Acquis"}
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey("AcademicClass", on_delete=models.PROTECT)
    enrollment = models.ForeignKey("Enrollment", on_delete=models.PROTECT)
    competency = models.ForeignKey(PreschoolCompetency, on_delete=models.PROTECT)
    day = models.DateField()
    stage = models.CharField(max_length=16, choices=list(STAGES.items()))
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["classroom", "enrollment", "competency", "day"],
            name="unique_preschool_competency_mark",
        )]


class PreschoolLiaisonMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey("AcademicClass", on_delete=models.PROTECT)
    enrollment = models.ForeignKey("Enrollment", on_delete=models.PROTECT)
    day = models.DateField()
    message = models.CharField(max_length=600)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["classroom", "enrollment", "day", "message"],
            name="unique_preschool_liaison_message",
        )]
