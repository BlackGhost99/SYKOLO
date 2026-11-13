"""Photo privée unique du membre du personnel, réutilisée par l'espace professeur."""
from django.db import migrations, models
import django.db.models.deletion


def enable_photo_rls(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            'ALTER TABLE "public"."institutions_staffphoto" ENABLE ROW LEVEL SECURITY'
        )


class Migration(migrations.Migration):
    dependencies = [("institutions", "0043_staff_professional_dossier")]

    operations = [
        migrations.CreateModel(
            name="StaffPhoto",
            fields=[
                ("staff", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True, serialize=False,
                    related_name="photo", to="institutions.staffrecord",
                )),
                ("data", models.BinaryField()),
                ("content_type", models.CharField(max_length=20)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(enable_photo_rls, migrations.RunPython.noop),
    ]
