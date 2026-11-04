"""Parent admission fees, optional gateway and auditable payment attempts."""
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


def secure_new_parent_tables(apps, schema_editor):
    """RLS defence-in-depth for newly created tables on Supabase/PostgreSQL."""
    if schema_editor.connection.vendor != "postgresql":
        return
    for name in ("SchoolAdmissionFee", "SchoolPaymentGateway", "ParentPaymentAttempt"):
        model = apps.get_model("institutions", name)
        schema_editor.execute(
            "ALTER TABLE %s ENABLE ROW LEVEL SECURITY"
            % schema_editor.quote_name(model._meta.db_table)
        )


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0018_school_appointments"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="parentadmissionrequest",
            name="fee_amount_xaf",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="parentadmissionrequest",
            name="payment_choice",
            field=models.CharField(
                choices=[("cash", "Espèces sur place"), ("online", "Mobile Money en ligne")],
                default="cash", max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="SchoolAdmissionFee",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount_xaf", models.PositiveIntegerField()),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("level", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="parent_admission_fees", to="institutions.academiclevel")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="parent_admission_fees", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="parent_admission_fees", to="institutions.academicyear")),
            ],
        ),
        migrations.AddConstraint(
            model_name="schooladmissionfee",
            constraint=models.UniqueConstraint(fields=("school", "year", "level"), name="unique_parent_admission_fee_scope"),
        ),
        migrations.AddConstraint(
            model_name="schooladmissionfee",
            constraint=models.CheckConstraint(condition=Q(amount_xaf__gte=100, amount_xaf__lte=10000000), name="parent_admission_fee_range"),
        ),
        migrations.CreateModel(
            name="SchoolPaymentGateway",
            fields=[
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True, related_name="admission_gateway", serialize=False, to="institutions.school")),
                ("provider", models.CharField(default="paycentral", max_length=24)),
                ("mode", models.CharField(choices=[("sandbox", "Simulation"), ("live", "Production")], default="sandbox", max_length=8)),
                ("encrypted_api_key", models.TextField(blank=True)),
                ("encrypted_webhook_secret", models.TextField(blank=True)),
                ("enabled", models.BooleanField(default=False)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ParentPaymentAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount_xaf", models.PositiveIntegerField()),
                ("currency", models.CharField(default="XAF", max_length=3)),
                ("provider", models.CharField(default="paycentral", max_length=24)),
                ("provider_mode", models.CharField(default="sandbox", max_length=8)),
                ("channel", models.CharField(choices=[("airtel", "Airtel Money"), ("moov", "Moov Money")], max_length=16)),
                ("payer_phone", models.CharField(max_length=24)),
                ("merchant_reference", models.CharField(max_length=48, unique=True)),
                ("transaction_id", models.CharField(blank=True, max_length=120, null=True, unique=True)),
                ("state", models.CharField(choices=[
                    ("initiating", "En cours d'initiation"), ("pending", "En attente de confirmation"),
                    ("unknown", "À rapprocher"), ("success", "Confirmé par le prestataire"),
                    ("failed", "Échoué"), ("cancelled", "Annulé"), ("refunded", "Remboursé")
                ], default="initiating", max_length=16)),
                ("provider_reference", models.CharField(blank=True, max_length=140)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="parent_payment_attempts", to=settings.AUTH_USER_MODEL)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_attempts", to="institutions.parentadmissionrequest")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="parent_payment_attempts", to="institutions.school")),
            ],
        ),
        migrations.AddIndex(
            model_name="parentpaymentattempt",
            index=models.Index(fields=["school", "state"], name="yem_parentpay_school_state"),
        ),
        migrations.AddConstraint(
            model_name="parentpaymentattempt",
            constraint=models.CheckConstraint(condition=Q(amount_xaf__gte=100, amount_xaf__lte=10000000), name="parent_payment_amount_range"),
        ),
        migrations.RunPython(secure_new_parent_tables, migrations.RunPython.noop),
    ]
