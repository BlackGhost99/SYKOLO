from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def protect_commercial(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in ("institutions_platformsubscriptionamendment", "institutions_platformsubscriptiontrial"):
            cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
            for role in ("anon", "authenticated"):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
                if cursor.fetchone():
                    cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0074_secondary_mastery"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="PlatformSubscriptionAmendment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("revision", models.PositiveIntegerField()),
                ("effective_on", models.DateField()),
                ("snapshot", models.JSONField()),
                ("amount_xaf", models.PositiveBigIntegerField()),
                ("reason", models.CharField(max_length=240)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("issued_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="amendments", to="institutions.platformsubscription")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("subscription", "revision"), name="unique_yem_amendment_revision")]},
        ),
        migrations.CreateModel(
            name="PlatformSubscriptionTrial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starts_on", models.DateField()),
                ("ends_before", models.DateField()),
                ("reason", models.CharField(max_length=240)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("issued_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="commercial_trial", to="institutions.school")),
                ("year", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="commercial_trial", to="institutions.academicyear")),
            ],
            options={"constraints": [models.CheckConstraint(condition=models.Q(ends_before__gt=models.F("starts_on")), name="valid_yem_trial_dates")]},
        ),
        migrations.RunPython(protect_commercial, migrations.RunPython.noop),
    ]
