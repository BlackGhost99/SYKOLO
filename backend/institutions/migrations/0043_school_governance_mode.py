"""Régime public / privé gabonais ; les établissements existants restent privés par défaut."""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("institutions", "0042_admission_finance_scholarship")]

    operations = [
        migrations.AddField(
            model_name="school",
            name="governance_mode",
            field=models.CharField(
                choices=[
                    ("public", "Public"),
                    ("prive_laique", "Privé laïc"),
                    ("prive_confessionnel", "Privé confessionnel"),
                ],
                default="prive_laique",
                max_length=24,
            ),
        ),
    ]
