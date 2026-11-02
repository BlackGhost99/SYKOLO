"""Immutable-at-publication student report snapshots."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import School
from .academic_models import AcademicYear, AcademicPeriod
from .student_models import Enrollment


class SchoolReport(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    school=models.ForeignKey(School,on_delete=models.PROTECT,related_name="reports")
    enrollment=models.ForeignKey(Enrollment,on_delete=models.PROTECT,related_name="reports")
    year=models.ForeignKey(AcademicYear,on_delete=models.PROTECT,related_name="reports")
    period=models.ForeignKey(AcademicPeriod,on_delete=models.PROTECT,null=True,blank=True,related_name="reports")
    period_key=models.CharField(max_length=36,blank=True)
    status=models.CharField(max_length=12,default="draft")
    snapshot=models.JSONField()
    revision=models.PositiveIntegerField(default=1)
    prepared_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="reports_prepared")
    created_at=models.DateTimeField(auto_now_add=True)
    published_at=models.DateTimeField(null=True,blank=True)

    class Meta:
        constraints=[
            models.UniqueConstraint(fields=["school","enrollment","year","period_key"],name="unique_report_enrollment_period")
        ]

    def clean(self):
        if self.status not in ("draft","published"):
            raise ValidationError("Statut de publication invalide.")
        if self.school_id and self.enrollment_id and self.enrollment.school_id!=self.school_id:
            raise ValidationError("Élève d'un autre établissement.")
        if self.school_id and self.year_id and self.year.school_id!=self.school_id:
            raise ValidationError("Année d'un autre établissement.")
        if self.enrollment_id and self.year_id and self.enrollment.year_id!=self.year_id:
            raise ValidationError("Inscription d'une autre année.")
        if self.period_id and self.year_id and (
            self.period.school_id!=self.school_id or self.period.year_id!=self.year_id
        ):
            raise ValidationError("Période d'un autre établissement ou année.")
        if self.period_key != (str(self.period_id) if self.period_id else ""):
            raise ValidationError("Identifiant de période incohérent.")
