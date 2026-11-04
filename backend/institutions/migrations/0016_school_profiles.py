"""Classification administrative et cycles enseignés, sans altérer les écoles existantes."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0015_admission_routes"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="school_type",
            field=models.CharField(
                max_length=32, default="non_classe",
                choices=[
                    ("non_classe", "À classifier"),
                    ("maternelle", "Maternelle"),
                    ("primaire", "École primaire"),
                    ("college", "Collège"),
                    ("lycee_general", "Lycée général"),
                    ("lycee_technique", "Lycée technique ou professionnel"),
                    ("groupe_scolaire", "Groupe scolaire / établissement mixte"),
                ],
            ),
        ),
        migrations.AddField(
            model_name="school",
            name="education_cycles",
            field=models.JSONField(default=list, blank=True),
        ),
    ]
