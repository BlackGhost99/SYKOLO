"""School-scoped assessments and draft grade entries.

A snapshot of the configured grading policy is mandatory to preserve historical meaning.
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import School
from .academic_models import AcademicPeriod
from .curriculum_models import CourseOffering
from .student_models import Enrollment


class Assessment(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    school=models.ForeignKey(School,on_delete=models.PROTECT,related_name="assessments")
    course=models.ForeignKey(CourseOffering,on_delete=models.PROTECT,related_name="assessments")
    period=models.ForeignKey(AcademicPeriod,on_delete=models.PROTECT,null=True,blank=True,related_name="assessments")
    name=models.CharField(max_length=180)
    kind=models.SlugField(max_length=50,default="evaluation")
    assessment_date=models.DateField()
    weight=models.DecimalField(max_digits=7,decimal_places=3,default=Decimal("1"))
    policy_snapshot=models.JSONField()
    policy_layers=models.JSONField(default=list)
    active=models.BooleanField(default=True)
    published=models.BooleanField(default=False)
    revision=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.school_id and self.course_id:
            if self.course.school_id!=self.school_id:
                raise ValidationError("Cours d'un autre établissement.")
            year=self.course.year
            if self.assessment_date and not (year.start_date<=self.assessment_date<=year.end_date):
                raise ValidationError("Date d'évaluation hors de l'année scolaire.")
        if self.period_id and self.course_id and (
            self.period.school_id!=self.school_id or self.period.year_id!=self.course.year_id
        ):
            raise ValidationError("La période doit appartenir à la même année et école.")
        if self.period_id and self.assessment_date and not (
            self.period.start_date<=self.assessment_date<=self.period.end_date
        ):
            raise ValidationError("Évaluation hors de la période choisie.")
        if self.weight is not None and not Decimal("0")<self.weight<=Decimal("1000"):
            raise ValidationError("Pondération invalide.")


class AssessmentGrade(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    school=models.ForeignKey(School,on_delete=models.PROTECT,related_name="grades")
    assessment=models.ForeignKey(Assessment,on_delete=models.PROTECT,related_name="grades")
    enrollment=models.ForeignKey(Enrollment,on_delete=models.PROTECT,related_name="grades")
    score=models.JSONField(null=True,blank=True)
    feedback=models.CharField(max_length=500,blank=True)
    status=models.CharField(max_length=24,default="empty")
    percent=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    label=models.CharField(max_length=120,blank=True)
    revision=models.PositiveIntegerField(default=1)
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="grades_entered")
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["assessment","enrollment"],name="unique_grade_by_assessment_enrollment")]

    def clean(self):
        if self.assessment_id and self.school_id and self.assessment.school_id!=self.school_id:
            raise ValidationError("Évaluation d'un autre établissement.")
        if self.enrollment_id and self.school_id and self.enrollment.school_id!=self.school_id:
            raise ValidationError("Inscription d'un autre établissement.")
        if self.enrollment_id and self.assessment_id and (
            self.enrollment.year_id!=self.assessment.course.year_id or
            self.enrollment.classroom_id!=self.assessment.course.classroom_id
        ):
            raise ValidationError("L'élève n'est pas inscrit dans la classe et l'année de cette évaluation.")
