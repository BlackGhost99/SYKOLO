"""M2.5: partial scholarships and discounted tuition charges.

Historical awards default to total coverage (100%). Existing fee charges
retain their full billed amount and start with zero subsidy.
"""
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("institutions", "0045_student_access_separation")]

    operations = [
        migrations.AddField(
            model_name="governmentscholarship",
            name="calculation",
            field=models.CharField(max_length=10, default="percent",
                choices=[("percent", "Pourcentage"), ("fixed", "Montant FCFA")]),
        ),
        migrations.AddField(
            model_name="governmentscholarship",
            name="percentage",
            field=models.PositiveSmallIntegerField(default=100),
        ),
        migrations.AddField(
            model_name="governmentscholarship",
            name="fixed_amount_xaf",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="governmentscholarship",
            name="allocations",
            field=models.JSONField(default=dict, blank=True),
        ),
        migrations.AlterField(
            model_name="governmentscholarship",
            name="coverage",
            field=models.CharField(max_length=16, default="all", choices=[
                ("all", "Tous les frais"),
                ("admission", "Frais d'inscription seulement"),
                ("tuition", "Frais de scolarité uniquement"),
            ]),
        ),
        migrations.AddField(
            model_name="feecharge",
            name="scholarship_discount",
            field=models.DecimalField(max_digits=12, decimal_places=2, default=0),
        ),
        migrations.AddConstraint(
            model_name="feecharge",
            constraint=models.CheckConstraint(condition=Q(scholarship_discount__gte=0),
                name="fee_charge_scholarship_nonnegative"),
        ),
    ]
