import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

def grant_admissions(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    mapping = {
        "direction": ["school.admissions.read", "school.admissions.manage", "school.admissions.decide", "school.admissions.enroll"],
        "secretariat": ["school.admissions.read", "school.admissions.manage", "school.admissions.enroll"],
    }
    for role in Role.objects.filter(code__in=mapping, revision=1).iterator():
        new = [permission for permission in mapping[role.code] if permission not in role.permissions]
        if new:
            role.permissions = list(role.permissions) + new
            role.save(update_fields=["permissions"])

class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0011_timetables"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="AdmissionApplication",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("first_name", models.CharField(max_length=120)),
                ("last_name", models.CharField(max_length=120)),
                ("date_of_birth", models.DateField(null=True, blank=True)),
                ("guardian_name", models.CharField(max_length=180)),
                ("guardian_relationship", models.CharField(blank=True, max_length=80)),
                ("guardian_phone", models.CharField(blank=True, max_length=45)),
                ("guardian_email", models.EmailField(blank=True, max_length=254)),
                ("source", models.SlugField(max_length=48)),
                ("status", models.CharField(choices=[("submitted", "Déposée"), ("review", "En cours d'étude"), ("accepted", "Admise"), ("rejected", "Refusée"), ("enrolled", "Inscrite")], default="submitted", max_length=16)),
                ("decision_reason", models.CharField(blank=True, max_length=1000)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("decided_at", models.DateTimeField(null=True, blank=True)),
                ("converted_at", models.DateTimeField(null=True, blank=True)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="institutions.academicyear")),
                ("classroom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="institutions.academicclass")),
                ("existing_student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="institutions.student")),
                ("enrollment", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="admission_application", to="institutions.enrollment")),
                ("submitted_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes":[models.Index(fields=["school", "year", "classroom", "status"], name="admission_workflow_idx")]},
        ),
        migrations.CreateModel(
            name="AdmissionEvent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("previous_status", models.CharField(blank=True, max_length=16)),
                ("new_status", models.CharField(max_length=16)),
                ("reason", models.CharField(blank=True, max_length=1000)),
                ("at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_events", to="institutions.school")),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="institutions.admissionapplication")),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["at", "id"]},
        ),
        migrations.RunPython(grant_admissions, migrations.RunPython.noop),
    ]
