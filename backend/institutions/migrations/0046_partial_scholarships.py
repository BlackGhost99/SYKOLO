"""M2.5: partial scholarships and discounted tuition charges.

Historical awards default to total coverage (100%). Existing fee charges
retain their full billed amount and start with zero subsidy.
"""
from django.db import migrations, models
from django.db.models import Q


def backfill_cash_applications(apps, schema_editor):
    Cash = apps.get_model('institutions', 'AdmissionCashReceipt')
    for receipt in Cash.objects.using(schema_editor.connection.alias).filter(
        request__isnull=False, application__isnull=True,
    ).select_related('request').iterator():
        receipt.application_id = receipt.request.application_id
        receipt.save(update_fields=['application'])


class Migration(migrations.Migration):
    dependencies = [("institutions", "0045_student_access_separation")]

    operations = [
        migrations.AddField(
            model_name="admissionapplication",
            name="admission_fee_snapshot_xaf",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
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
        migrations.AlterField(
            model_name="admissioncashreceipt",
            name="request",
            field=models.OneToOneField(
                to="institutions.parentadmissionrequest", on_delete=models.PROTECT,
                null=True, blank=True, related_name="cash_receipt",
            ),
        ),
        migrations.AddField(
            model_name="admissioncashreceipt",
            name="application",
            field=models.OneToOneField(
                to="institutions.admissionapplication", on_delete=models.PROTECT,
                null=True, blank=True, related_name="admission_cash_receipt",
            ),
        ),
        migrations.RunPython(backfill_cash_applications, migrations.RunPython.noop),
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
