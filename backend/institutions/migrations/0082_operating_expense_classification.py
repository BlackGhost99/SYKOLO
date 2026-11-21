"""B2: additive, non-destructive activity classification for school expenses.

Legacy transactions remain "unclassified"; no fabricated allocation is introduced.
Branch depends on institutions/0081. Rebase and reconcile the migration graph
with all parallel PRs before merging.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("institutions", "0081_gemini_daily_usage")]

    operations = [
        migrations.AddField(
            model_name="operatingexpense",
            name="activity_pole",
            field=models.CharField(
                choices=[
                    ("unclassified", "À classer (historique)"),
                    ("school", "Scolarité"),
                    ("extraschool", "Extrascolaire"),
                    ("common", "Administration et charges communes"),
                    ("investment", "Investissements"),
                    ("cash_other", "Autres sorties de trésorerie"),
                ],
                default="unclassified", max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="operatingexpense",
            name="cost_center",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="operatingexpense",
            name="accounting_nature",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
