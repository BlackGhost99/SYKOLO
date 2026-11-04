from django.db import migrations, models
import django.db.models


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0015_admission_routes"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="school_type",
            field=models.CharField(
                choices=[
                    ("a_configurer", "Type à configurer"),
                    ("maternelle", "Maternelle"),
                    ("primaire", "École primaire"),
                    ("college", "Collège"),
                    ("lycee", "Lycée"),
                    ("groupe_scolaire", "Groupe scolaire / multicycle"),
                ],
                default="a_configurer",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="school",
            name="enabled_cycles",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="school",
            name="profile_revision",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
