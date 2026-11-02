import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def grant_attendance(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    mapping = {
        "direction": ["school.attendance.read", "school.attendance.write", "school.attendance.finalize"],
        "secretariat": ["school.attendance.read", "school.attendance.write"],
    }
    for role in Role.objects.filter(code__in=mapping, revision=1).iterator():
        additions = [p for p in mapping[role.code] if p not in role.permissions]
        if additions:
            role.permissions = list(role.permissions) + additions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0009_finance_ledger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="AttendanceSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("attendance_date", models.DateField()),
                ("slot", models.SlugField(max_length=48)),
                ("label", models.CharField(max_length=120)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("closed_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attendance_sessions", to="institutions.school")),
                ("classroom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attendance_sessions", to="institutions.academicclass")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("closed_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="AttendanceMark",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status_code", models.SlugField(max_length=48)),
                ("status_label", models.CharField(max_length=120)),
                ("status_group", models.SlugField(max_length=16)),
                ("note", models.CharField(max_length=500, blank=True)),
                ("justification", models.CharField(max_length=500, blank=True)),
                ("justified", models.BooleanField(default=False)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attendance_marks", to="institutions.school")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="marks", to="institutions.attendancesession")),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attendance_marks", to="institutions.enrollment")),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="AttendanceChange",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("revision", models.PositiveIntegerField()),
                ("before", models.JSONField(null=True, blank=True)),
                ("after", models.JSONField()),
                ("reason", models.CharField(max_length=500, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="institutions.school")),
                ("mark", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="changes", to="institutions.attendancemark")),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["revision"]},
        ),
        migrations.AddConstraint(
            model_name="attendancesession",
            constraint=models.UniqueConstraint(fields=("school", "classroom", "attendance_date", "slot"),
                                               name="unique_attendance_class_date_slot"),
        ),
        migrations.AddConstraint(
            model_name="attendancemark",
            constraint=models.UniqueConstraint(fields=("school", "session", "enrollment"),
                                               name="unique_attendance_mark_per_session"),
        ),
        migrations.AddConstraint(
            model_name="attendancechange",
            constraint=models.UniqueConstraint(fields=("mark", "revision"), name="unique_attendance_mark_change"),
        ),
        migrations.RunPython(grant_attendance, migrations.RunPython.noop),
    ]
