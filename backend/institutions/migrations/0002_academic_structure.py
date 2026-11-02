import uuid
from django.db import migrations, models
import django.db.models.deletion


def grant_academic_permissions(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    role_permissions = {
        "direction": ("school.academic.read", "school.academic.manage"),
        "secretariat": ("school.academic.read",),
        "enseignant": ("school.academic.read",),
    }
    for role in Role.objects.filter(revision=1, code__in=role_permissions.keys()).iterator():
        current = list(role.permissions)
        added = [p for p in role_permissions[role.code] if p not in current]
        if added:
            role.permissions = current + added
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("institutions", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="AcademicYear",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academic_years", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="AcademicCycle",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academic_cycles", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="AcademicLevel",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("cycle", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="levels", to="institutions.academiccycle")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academic_levels", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="AcademicTrack",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("level", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tracks", to="institutions.academiclevel")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academic_tracks", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="AcademicClass",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("capacity", models.PositiveIntegerField(null=True, blank=True)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="classes", to="institutions.academicyear")),
                ("level", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="classes", to="institutions.academiclevel")),
                ("track", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="classes", to="institutions.academictrack", null=True, blank=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academic_classes", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="AcademicPeriod",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="periods", to="institutions.academicyear")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academic_periods", to="institutions.school")),
            ],
        ),
        migrations.AddConstraint("academicyear", models.UniqueConstraint(fields=("school", "code"), name="unique_academic_year_code")),
        migrations.AddConstraint("academiccycle", models.UniqueConstraint(fields=("school", "code"), name="unique_academic_cycle_code")),
        migrations.AddConstraint("academiclevel", models.UniqueConstraint(fields=("cycle", "code"), name="unique_academic_level_code")),
        migrations.AddConstraint("academictrack", models.UniqueConstraint(fields=("level", "code"), name="unique_academic_track_code")),
        migrations.AddConstraint("academicclass", models.UniqueConstraint(fields=("year", "code"), name="unique_academic_class_code")),
        migrations.AddConstraint("academicperiod", models.UniqueConstraint(fields=("year", "code"), name="unique_academic_period_code")),
        migrations.RunPython(grant_academic_permissions, migrations.RunPython.noop),
    ]
