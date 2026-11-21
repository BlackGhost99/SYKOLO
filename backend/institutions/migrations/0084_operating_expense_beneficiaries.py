"""B3: expenses can target a non-commercial beneficiary without a fake supplier.

All existing expenses remain supplier expenses. Their FK and payments are retained.
No financial rows, balances, or receipts are rewritten.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("institutions", "0083_operating_expense_catalog")]

    operations = [
        migrations.AlterField(
            model_name="operatingexpense",
            name="supplier",
            field=models.ForeignKey(
                to="institutions.operatingsupplier", related_name="expenses",
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="beneficiary_type",
            field=models.CharField(max_length=20, default="supplier", choices=[
                ("supplier", "Fournisseur ou prestataire"),
                ("staff", "Membre du personnel (hors paie)"),
                ("government", "Administration ou organisme public"),
                ("parent", "Parent ou responsable légal"),
                ("individual", "Personne physique"),
                ("organization", "Organisation ou association"),
                ("other", "Autre bénéficiaire"),
            ]),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="beneficiary_name",
            field=models.CharField(max_length=180, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="beneficiary_reference",
            field=models.CharField(max_length=120, blank=True, default=""),
        ),
    ]
