"""Modular subjects, course offerings, teaching units and instructor links."""
import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from .models import School
from .academic_models import AcademicYear, AcademicClass
from .staff_models import StaffAssignment


class Subject(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    school=models.ForeignKey(School,on_delete=models.PROTECT,related_name="subjects")
    code=models.SlugField(max_length=50)
    name=models.CharField(max_length=120)
    description=models.CharField(max_length=500,blank=True)
    active=models.BooleanField(default=True)
    revision=models.PositiveIntegerField(default=1)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["school","code"],name="unique_school_subject")]


class CourseOffering(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    school=models.ForeignKey(School,on_delete=models.PROTECT,related_name="courses")
    year=models.ForeignKey(AcademicYear,on_delete=models.PROTECT,related_name="courses")
    classroom=models.ForeignKey(AcademicClass,on_delete=models.PROTECT,related_name="courses")
    subject=models.ForeignKey(Subject,on_delete=models.PROTECT,related_name="courses")
    coefficient=models.DecimalField(max_digits=7,decimal_places=3,default=Decimal("1.000"))
    active=models.BooleanField(default=True)
    revision=models.PositiveIntegerField(default=1)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["school","year","classroom","subject"],name="unique_school_class_subject")]

    def clean(self):
        if self.school_id:
            if self.year_id and self.year.school_id!=self.school_id:
                raise ValidationError("Année scolaire étrangère.")
            if self.classroom_id and (
                self.classroom.school_id!=self.school_id or self.classroom.year_id!=self.year_id
            ):
                raise ValidationError("Classe et année incohérentes.")
            if self.subject_id and self.subject.school_id!=self.school_id:
                raise ValidationError("Matière d'un autre établissement.")
        if self.coefficient is not None and not (Decimal("0")<self.coefficient<=Decimal("1000")):
            raise ValidationError("Coefficient hors limites.")


class CourseUnit(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    school=models.ForeignKey(School,on_delete=models.PROTECT,related_name="course_units")
    course=models.ForeignKey(CourseOffering,on_delete=models.PROTECT,related_name="units")
    code=models.SlugField(max_length=50)
    title=models.CharField(max_length=180)
    objectives=models.TextField(max_length=2000,blank=True)
    order=models.PositiveSmallIntegerField(default=0)
    active=models.BooleanField(default=True)
    revision=models.PositiveIntegerField(default=1)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["course","code"],name="unique_course_unit_code")]

    def clean(self):
        if self.course_id and self.school_id and self.course.school_id!=self.school_id:
            raise ValidationError("Programme appartenant à un autre établissement.")


class CourseInstructor(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    school=models.ForeignKey(School,on_delete=models.PROTECT,related_name="course_instructors")
    course=models.ForeignKey(CourseOffering,on_delete=models.PROTECT,related_name="instructors")
    staff_assignment=models.ForeignKey(StaffAssignment,on_delete=models.PROTECT,related_name="courses")
    active=models.BooleanField(default=True)
    revision=models.PositiveIntegerField(default=1)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["course","staff_assignment"],name="unique_course_staff_link")]

    def clean(self):
        if self.course_id and self.school_id and self.course.school_id!=self.school_id:
            raise ValidationError("Cours d'un autre établissement.")
        if self.staff_assignment_id and self.school_id and (
            self.staff_assignment.school_id!=self.school_id or
            self.staff_assignment.classroom_id!=self.course.classroom_id or
            self.staff_assignment.year_id!=self.course.year_id
        ):
            raise ValidationError("L'enseignant doit être affecté à cette classe et cette année.")
        if self.active and self.staff_assignment_id and not self.staff_assignment.active:
            raise ValidationError("Affectation du personnel inactive.")
