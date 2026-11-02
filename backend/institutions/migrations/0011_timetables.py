import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


def grant_timetables(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    mapping = {
        "direction": ["school.timetable.read", "school.timetable.manage"],
        "secretariat": ["school.timetable.read", "school.timetable.manage"],
        "enseignant": ["school.timetable.read"],
    }
    # Preserve customized roles
    for role in Role.objects.filter(code__in=mapping, revision=1).iterator():
        additions = [p for p in mapping[role.code] if p not in role.permissions]
        if additions:
            role.permissions = list(role.permissions) + additions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0010_attendance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="TimetableRoom",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=48)),
                ("name", models.CharField(max_length=120)),
                ("capacity", models.PositiveIntegerField(null=True, blank=True)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_rooms", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="TimetableSlot",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=48)),
                ("label", models.CharField(max_length=120)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_slots", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_slots", to="institutions.academicyear")),
            ],
        ),
        migrations.CreateModel(
            name="TimetableEntry",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("weekday", models.PositiveSmallIntegerField()),
                ("effective_from", models.DateField()),
                ("effective_to", models.DateField()),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_entries", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_entries", to="institutions.academicyear")),
                ("classroom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_entries", to="institutions.academicclass")),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_entries", to="institutions.courseoffering")),
                ("instructor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timetable_entries", to="institutions.courseinstructor")),
                ("slot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entries", to="institutions.timetableslot")),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="entries", to="institutions.timetableroom")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [models.Index(fields=["school", "year", "weekday", "active"], name="timetable_weekly_idx")]},
        ),
        migrations.AddConstraint("timetableroom", models.UniqueConstraint(fields=("school", "code"), name="unique_school_timetable_room")),
        migrations.AddConstraint("timetableslot", models.UniqueConstraint(fields=("school", "year", "code"), name="unique_school_year_slot")),
        migrations.AddConstraint("timetableentry", models.CheckConstraint(condition=Q(weekday__gte=0, weekday__lte=6), name="timetable_weekday_bounds")),
        migrations.AddConstraint("timetableentry", models.CheckConstraint(condition=Q(effective_to__gte=models.F("effective_from")), name="timetable_effective_bounds")),
        migrations.RunPython(grant_timetables, migrations.RunPython.noop),
    ]
