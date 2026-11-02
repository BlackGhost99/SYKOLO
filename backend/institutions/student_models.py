"""School-scoped learner and admission records. No medical information is stored."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import School
from .academic_models import AcademicYear, AcademicClass


class Student(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="students")
    student_code = models.SlugField(max_length=50)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    date_of_birth = models.DateField(null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "student_code"], name="unique_school_student_code"),
        ]


class StudentGuardian(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="guardians")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="guardians")
    full_name = models.CharField(max_length=180)
    relationship = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=45, blank=True)
    email = models.EmailField(blank=True)
    is_primary = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)

    def clean(self):
        if self.student_id and self.school_id and self.student.school_id != self.school_id:
            raise ValidationError("Le responsable légal appartient à une autre école.")


class Enrollment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="enrollments")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="enrollments")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="enrollments")
    classroom = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="enrollments")
    enrolled_on = models.DateField()
    status = models.SlugField(max_length=40, default="inscrit")
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "student", "year"], name="unique_student_school_year_enrollment"),
        ]

    def clean(self):
        if self.school_id and self.student_id and self.student.school_id != self.school_id:
            raise ValidationError("L'élève appartient à une autre école.")
        if self.school_id and self.year_id and self.year.school_id != self.school_id:
            raise ValidationError("L'année appartient à une autre école.")
        if self.classroom_id and self.school_id:
            if self.classroom.school_id != self.school_id or self.classroom.year_id != self.year_id:
                raise ValidationError("La classe doit être dans la même école et année.")
        if self.year_id and self.enrolled_on and self.active:
            if not (self.year.start_date <= self.enrolled_on <= self.year.end_date):
                raise ValidationError("La date d'inscription doit être dans l'année scolaire.")


class EnrollmentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="history")
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    previous_class_id = models.UUIDField(null=True)
    new_class_id = models.UUIDField()
    previous_status = models.CharField(max_length=40, blank=True)
    new_status = models.CharField(max_length=40)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]
