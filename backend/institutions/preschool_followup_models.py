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
