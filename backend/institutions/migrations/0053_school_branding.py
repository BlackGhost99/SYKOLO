"""Stockage prive et isole du logo et de la banniere d'un etablissement YEM."""
import django.db.models.deletion
from django.db import migrations, models


def private_school_branding(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'ALTER TABLE "public"."institutions_schoolbranding" ENABLE ROW LEVEL SECURITY'
        )
        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
        for (role,) in cursor.fetchall():
            cursor.execute(
                f'REVOKE ALL PRIVILEGES ON TABLE "public"."institutions_schoolbranding" FROM "{role}"'
            )


class Migration(migrations.Migration):
    dependencies = [("institutions", "0052_operating_budget_expenses")]

    operations = [
        migrations.CreateModel(
            name="SchoolBranding",
            fields=[
                ("school", models.OneToOneField(
                    to="institutions.school", primary_key=True, serialize=False,
                    on_delete=django.db.models.deletion.CASCADE, related_name="branding",
                )),
                ("city", models.CharField(max_length=120, blank=True, default="")),
                ("tagline", models.CharField(max_length=160, blank=True, default="")),
                ("logo_data", models.BinaryField(null=True, blank=True)),
                ("logo_content_type", models.CharField(max_length=30, blank=True, default="")),
                ("banner_data", models.BinaryField(null=True, blank=True)),
                ("banner_content_type", models.CharField(max_length=30, blank=True, default="")),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(private_school_branding, migrations.RunPython.noop),
    ]
