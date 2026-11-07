"""School-scoped learner and admission records. No medical information is stored."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, router, transaction
from .models import School
from .academic_models import AcademicYear, AcademicClass


def yem_student_number(identity_id):
    return f"YEM-{identity_id.hex.upper()}"


class StudentIdentity(models.Model):
    """Platform identity shared only by explicitly linked local student files."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class Student(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="students")
    identity = models.ForeignKey(StudentIdentity, on_delete=models.PROTECT, editable=False, blank=True)
    student_code = models.SlugField(max_length=50, blank=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    date_of_birth = models.DateField(null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    # Fiche de renseignement (facultatif, aucune donnée médicale).
    gender = models.CharField(max_length=1, blank=True, choices=[("F", "Féminin"), ("M", "Masculin")])
    place_of_birth = models.CharField(max_length=120, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    address = models.CharField(max_length=255, blank=True)
    previous_school = models.CharField(max_length=180, blank=True)
    # Champs propres à l'établissement (formulaire modulable) et pièces fournies.
    extra_fields = models.JSONField(default=dict, blank=True)
    documents = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "student_code"], name="unique_school_student_code"),
            models.UniqueConstraint(fields=["school", "identity"], name="unique_school_student_identity"),
        ]

    @property
    def matricule_yem(self):
        return yem_student_number(self.identity_id or self.pk)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            return super().save(*args, **kwargs)
        database = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=database):
            if self.identity_id is None:
                self.identity = StudentIdentity.objects.using(database).create()
            if not self.student_code:
                self.student_code = self.matricule_yem
            return super().save(*args, **kwargs)


class StudentGuardian(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="guardians")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="guardians")
    full_name = models.CharField(max_length=180)
    relationship = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=45, blank=True)
    email = models.EmailField(blank=True)
    profession = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=255, blank=True)
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


class EnrollmentFormConfig(models.Model):
    """Formulaire d'inscription propre à chaque établissement, réglé par le secrétariat."""
    school = models.OneToOneField(School, on_delete=models.CASCADE, primary_key=True, related_name="enrollment_form")
    config = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
