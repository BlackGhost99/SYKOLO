import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def protect_progress(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as c:
        c.execute("ALTER TABLE public.institutions_courseunitprogress ENABLE ROW LEVEL SECURITY")
        c.execute("REVOKE ALL ON TABLE public.institutions_courseunitprogress FROM PUBLIC")
        for role in ("anon", "authenticated"):
            c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [role])
            if c.fetchone():
                c.execute(f'REVOKE ALL ON TABLE public.institutions_courseunitprogress FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0072_diary_resources"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="CourseUnitProgress",
            fields=[
                ("unit", models.OneToOneField(primary_key=True, serialize=False, on_delete=django.db.models.deletion.PROTECT, related_name="progress", to="institutions.courseunit")),
                ("planned_start", models.DateField(null=True, blank=True)),
                ("planned_end", models.DateField(null=True, blank=True)),
                ("status", models.CharField(max_length=16, choices=[("not_started","Non commencé"),("in_progress","En cours"),("completed","Dispensé")], default="not_started")),
                ("completed_on", models.DateField(null=True, blank=True)),
                ("evidence", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="unit_progress", to="institutions.teachingdiaryentry")),
                ("updated_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"constraints":[
                models.CheckConstraint(condition=models.Q(planned_start__isnull=True) | models.Q(planned_end__isnull=True) | models.Q(planned_end__gte=models.F("planned_start")), name="yem_progress_plan_dates"),
                models.CheckConstraint(condition=models.Q(status="completed", completed_on__isnull=False) | models.Q(status__in=["not_started","in_progress"], completed_on__isnull=True), name="yem_progress_completion"),
            ]},
        ),
        migrations.RunPython(protect_progress, migrations.RunPython.noop),
    ]
