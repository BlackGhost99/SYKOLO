from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as c:
        table = "institutions_platformcommercialaccessdecision"
        c.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        c.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
        for role in ("anon", "authenticated"):
            c.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if c.fetchone():
                c.execute(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0075_commercial_amendments_trials"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="PlatformCommercialAccessDecision", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("revision", models.PositiveIntegerField()),
            ("restricted", models.BooleanField()),
            ("reason", models.CharField(max_length=240)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(null=True, related_name="+", on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ("school", models.ForeignKey(related_name="commercial_access_decisions", on_delete=django.db.models.deletion.PROTECT, to="institutions.school")),
        ], options={"constraints":[models.UniqueConstraint(fields=("school","revision"), name="unique_yem_commercial_access_revision")]}),
        migrations.RunPython(protect, migrations.RunPython.noop),
    ]
