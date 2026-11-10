"""Isolated configurable admission payment simulations for named test parents only."""
from django.db import migrations, models
import django.db.models.deletion


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute('ALTER TABLE "institutions_schooldemopaymentconfig" ENABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0040_pedagogical_calendar")]

    operations = [
        migrations.CreateModel(
            name="SchoolDemoPaymentConfig",
            fields=[
                ("school", models.OneToOneField(
                    primary_key=True, serialize=False, on_delete=django.db.models.deletion.PROTECT,
                    related_name="demo_admission_config", to="institutions.school")),
                ("enabled", models.BooleanField(default=False)),
                ("level_amounts_xaf", models.JSONField(blank=True, default=dict)),
                ("allowed_parent_ids", models.JSONField(blank=True, default=list)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AlterField(
            model_name="parentadmissionrequest", name="payment_choice",
            field=models.CharField(
                max_length=16, default="cash",
                choices=[
                    ("cash", "Espèces sur place"),
                    ("online", "Mobile Money en ligne"),
                    ("demo", "Simulation YEM (aucun argent)"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="parentpaymentattempt", name="channel",
            field=models.CharField(
                max_length=16,
                choices=[
                    ("airtel", "Airtel Money"),
                    ("moov", "Moov Money"),
                    ("demo", "Simulation YEM"),
                ],
            ),
        ),
        migrations.RunPython(enable_rls, migrations.RunPython.noop),
    ]
