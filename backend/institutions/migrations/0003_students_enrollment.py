import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def grant(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    mapping = {
        "direction": ["school.students.read", "school.students.manage"],
        "secretariat": ["school.students.read", "school.students.manage"],
    }
    for role in Role.objects.filter(code__in=mapping, revision=1).iterator():
        current = list(role.permissions)
        additions = [p for p in mapping[role.code] if p not in current]
        if additions:
            role.permissions = current + additions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("institutions", "0002_academic_structure"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Student",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, default=uuid.uuid4, editable=False)),
                ("student_code", models.SlugField(max_length=50)),
                ("first_name", models.CharField(max_length=120)),
                ("last_name", models.CharField(max_length=120)),
                ("date_of_birth", models.DateField(null=True, blank=True)),
                ("admission_date", models.DateField(null=True, blank=True)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="students", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="StudentGuardian",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, default=uuid.uuid4, editable=False)),
                ("full_name", models.CharField(max_length=180)),
                ("relationship", models.CharField(max_length=80, blank=True)),
                ("phone", models.CharField(max_length=45, blank=True)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("is_primary", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="guardians", to="institutions.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="guardians", to="institutions.student")),
            ],
        ),
        migrations.CreateModel(
            name="Enrollment",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, default=uuid.uuid4, editable=False)),
                ("enrolled_on", models.DateField()),
                ("status", models.SlugField(max_length=40, default="inscrit")),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="institutions.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="institutions.student")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="institutions.academicyear")),
                ("classroom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="institutions.academicclass")),
            ],
        ),
        migrations.CreateModel(
            name="EnrollmentEvent",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, default=uuid.uuid4, editable=False)),
                ("previous_class_id", models.UUIDField(null=True)),
                ("new_class_id", models.UUIDField()),
                ("previous_status", models.CharField(blank=True, max_length=40)),
                ("new_status", models.CharField(max_length=40)),
                ("at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="history", to="institutions.enrollment")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="institutions.school")),
            ],
            options={"ordering": ["-at"]},
        ),
        migrations.AddConstraint("student", models.UniqueConstraint(fields=("school", "student_code"), name="unique_school_student_code")),
        migrations.AddConstraint("enrollment", models.UniqueConstraint(fields=("school", "student", "year"), name="unique_student_school_year_enrollment")),
        migrations.RunPython(grant, migrations.RunPython.noop),
    ]
