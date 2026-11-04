"""Atomic, idempotent multi-fee cash entries. No mutation of historical payments."""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0016_school_profiles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FeePaymentBatch",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("idempotency_key", models.UUIDField()),
                ("request_hash", models.CharField(max_length=64)),
                ("total", models.DecimalField(max_digits=12, decimal_places=2)),
                ("currency", models.CharField(max_length=3)),
                ("method", models.SlugField(max_length=48)),
                ("reference", models.CharField(max_length=100, blank=True)),
                ("paid_on", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT, related_name="payment_batches")),
                ("enrollment", models.ForeignKey(to="institutions.enrollment", on_delete=django.db.models.deletion.PROTECT, related_name="payment_batches")),
                ("recorded_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("school", "idempotency_key"), name="unique_school_fee_batch_idempotency"),
                    models.CheckConstraint(condition=models.Q(total__gt=0), name="fee_payment_batch_total_positive"),
                ],
            },
        ),
        migrations.AddField(
            model_name="feepayment",
            name="batch",
            field=models.ForeignKey(to="institutions.feepaymentbatch", on_delete=django.db.models.deletion.PROTECT, related_name="lines", null=True, blank=True),
        ),
        migrations.AddConstraint(
            model_name="feepayment",
            constraint=models.UniqueConstraint(fields=("batch", "charge"), name="unique_charge_in_fee_batch"),
        ),
    ]
