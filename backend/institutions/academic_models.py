import uuid
from datetime import date
from django.core.exceptions import ValidationError
from django.db import models
from .models import School


class AcademicYear(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_years")
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()
    active = models.BooleanField(default=True)
    # The legacy 'active' flag remains for compatibility while the lifecycle
    # distinguishes an upcoming school year from the sole running year.
    STATUS_PREPARATION = "preparation"
    STATUS_CURRENT = "current"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_PREPARATION, "En préparation"),
        (STATUS_CURRENT, "En cours"),
        (STATUS_CLOSED, "Clôturée"),
    ]
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PREPARATION)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], name="unique_academic_year_code"),
            models.UniqueConstraint(
                fields=["school"], condition=models.Q(status="current"),
                name="unique_current_academic_year_per_school",
            ),
        ]

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({"end_date": "La fin doit suivre le début."})
        if self.pk and self.start_date and self.end_date:
            if AcademicPeriod.objects.filter(year=self).exclude(
                start_date__gte=self.start_date, end_date__lte=self.end_date
            ).exists():
                raise ValidationError("Des périodes sont hors de la nouvelle année.")


class AcademicCycle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_cycles")
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "code"], name="unique_academic_cycle_code")]


class AcademicLevel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_levels")
    cycle = models.ForeignKey(AcademicCycle, on_delete=models.PROTECT, related_name="levels")
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["cycle", "code"], name="unique_academic_level_code")]

    def clean(self):
        if self.cycle_id and self.school_id and self.cycle.school_id != self.school_id:
            raise ValidationError("Le cycle appartient à un autre établissement.")


class AcademicTrack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_tracks")
    level = models.ForeignKey(AcademicLevel, on_delete=models.PROTECT, related_name="tracks")
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["level", "code"], name="unique_academic_track_code")]

    def clean(self):
        if self.level_id and self.school_id and self.level.school_id != self.school_id:
            raise ValidationError("Le niveau appartient à un autre établissement.")


class AcademicClass(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_classes")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="classes")
    level = models.ForeignKey(AcademicLevel, on_delete=models.PROTECT, related_name="classes")
    track = models.ForeignKey(AcademicTrack, on_delete=models.PROTECT, null=True, blank=True, related_name="classes")
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["year", "code"], name="unique_academic_class_code")]

    def clean(self):
        if self.school_id and self.year_id and self.year.school_id != self.school_id:
            raise ValidationError("L'année appartient à un autre établissement.")
        if self.school_id and self.level_id and self.level.school_id != self.school_id:
            raise ValidationError("Le niveau appartient à un autre établissement.")
        if self.track_id and (self.track.school_id != self.school_id or self.track.level_id != self.level_id):
            raise ValidationError("La filière doit appartenir au même niveau et à la même école.")
        if self.capacity is not None and self.capacity < 1:
            raise ValidationError({"capacity": "La capacité doit être supérieure à zéro."})


class AcademicPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_periods")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="periods")
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["year", "code"], name="unique_academic_period_code")]

    def clean(self):
        if self.school_id and self.year_id and self.year.school_id != self.school_id:
            raise ValidationError("L'année appartient à un autre établissement.")
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError({"end_date": "La fin précède le début."})
            if self.year_id and not (self.year.start_date <= self.start_date <= self.end_date <= self.year.end_date):
                raise ValidationError("La période doit rester dans les dates de l'année.")
            if self.active and self.year_id and AcademicPeriod.objects.filter(
                year_id=self.year_id, active=True,
                start_date__lte=self.end_date, end_date__gte=self.start_date
            ).exclude(pk=self.pk).exists():
                raise ValidationError("Les périodes actives ne doivent pas se chevaucher.")
