"""School-scoped pilot cash receipts, independent of real tuition and PSP ledgers."""
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            for table in (
                "institutions_schooldemopaymentconfig",
                "institutions_admissioncashreceipt",
                "institutions_admissioncashreceiptvoid",
            ):
                cursor.execute('ALTER TABLE "' + table + '" ENABLE ROW LEVEL SECURITY')


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
        migrations.AddField(
            model_name="parentadmissionrequest",
            name="is_demo_cash",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="AdmissionCashReceipt",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("request", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="cash_receipt", to="institutions.parentadmissionrequest",
                )),
                ("school", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="admission_cash_receipts", to="institutions.school",
                )),
                ("amount_xaf", models.PositiveIntegerField()),
                ("is_demo", models.BooleanField(default=False)),
                ("reference", models.CharField(max_length=100, blank=True)),
                ("received_on", models.DateField()),
                ("recorded_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="admissioncashreceipt",
            constraint=models.CheckConstraint(
                condition=models.Q(amount_xaf__gte=100, amount_xaf__lte=10000000),
                name="admission_cash_receipt_amount_valid",
            ),
        ),
        migrations.CreateModel(
            name="AdmissionCashReceiptVoid",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("receipt", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="void", to="institutions.admissioncashreceipt",
                )),
                ("school", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="institutions.school",
                )),
                ("reason", models.CharField(max_length=1000)),
                ("voided_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.RunPython(enable_rls, migrations.RunPython.noop),
    ]
