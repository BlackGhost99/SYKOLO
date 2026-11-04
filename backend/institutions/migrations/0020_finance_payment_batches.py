"""Atomic, idempotent multi-fee cash entries. No mutation of historical payments."""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0019_parent_payments"),
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
        migrations.CreateModel(
            name="CashClosing",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("day", models.DateField()),
                ("currency", models.CharField(max_length=3)),
                ("expected", models.DecimalField(max_digits=12, decimal_places=2)),
                ("counted", models.DecimalField(max_digits=12, decimal_places=2)),
                ("difference", models.DecimalField(max_digits=13, decimal_places=2)),
                ("note", models.CharField(blank=True, max_length=500)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approval_note", models.CharField(blank=True, max_length=500)),
                ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT, related_name="cash_closings")),
                ("submitted_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="yem_cash_closings_submitted")),
                ("approved_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, related_name="yem_cash_closings_approved", null=True, blank=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("school", "day", "currency", "submitted_by"), name="unique_school_cash_closing_per_cashier"),
                    models.CheckConstraint(condition=models.Q(expected__gte=0), name="cash_closing_expected_nonnegative"),
                    models.CheckConstraint(condition=models.Q(counted__gte=0), name="cash_closing_counted_nonnegative"),
                ],
            },
        ),
    ]
