import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def protect_diary(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('ALTER TABLE public.institutions_teachingdiaryentry ENABLE ROW LEVEL SECURITY')
        cursor.execute('REVOKE ALL ON TABLE public.institutions_teachingdiaryentry FROM PUBLIC')
        for role in ("anon", "authenticated"):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [role])
            if cursor.fetchone():
                cursor.execute(f'REVOKE ALL ON TABLE public.institutions_teachingdiaryentry FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0070_commercial_tariff_policy"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="TeachingDiaryEntry",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("day", models.DateField()),
                ("title", models.CharField(max_length=180)),
                ("lesson", models.TextField(max_length=4000)),
                ("homework", models.TextField(max_length=4000, blank=True)),
                ("due_on", models.DateField(null=True, blank=True)),
                ("published", models.BooleanField(default=False)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("author", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="diary_entries", to="institutions.courseoffering")),
            ],
            options={"indexes":[models.Index(fields=["course", "-day"], name="yem_diary_course_day_idx")], "constraints":[models.CheckConstraint(condition=models.Q(due_on__isnull=True) | models.Q(due_on__gte=models.F("day")), name="yem_diary_due_after_day")]},
        ),
        migrations.RunPython(protect_diary, migrations.RunPython.noop),
    ]
