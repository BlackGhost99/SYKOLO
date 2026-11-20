from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0077_commercial_singpay"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoricalFinancialMigration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("cutoff", models.DateField()),
                ("fingerprint", models.CharField(max_length=64)),
                ("status", models.CharField(default="prepared", max_length=16)),
                ("source_reference", models.CharField(max_length=255)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("prepared_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancellation_reason", models.CharField(blank=True, max_length=1000)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="historical_migrations_approved", to=settings.AUTH_USER_MODEL)),
                ("prepared_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_migrations_prepared", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_migrations", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_migrations", to="institutions.academicyear")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("school", "fingerprint"), name="unique_school_historical_migration_fingerprint"),
                    models.CheckConstraint(condition=django.db.models.expressions.Q(("status__in", ["prepared", "approved", "cancelled"])), name="historical_migration_status"),
                ],
            },
        ),
        migrations.CreateModel(
            name="HistoricalFinancialMigrationEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_row", models.PositiveIntegerField()),
                ("state", models.CharField(max_length=32)),
                ("declared_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("net_due", models.DecimalField(decimal_places=2, max_digits=12)),
                ("scholarship", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("evidence_reference", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entries", to="institutions.historicalfinancialmigration")),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_migration_entries", to="institutions.enrollment")),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_migration_entries", to="institutions.feeschedule")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_migration_entries", to="institutions.school")),
                ("charge", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="historical_migration_entries", to="institutions.feecharge")),
            ],
        ),
        migrations.CreateModel(
            name="HistoricalFeeAdjustment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("cutoff", models.DateField()),
                ("evidence_reference", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_fee_adjustments", to=settings.AUTH_USER_MODEL)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_adjustments", to="institutions.historicalfinancialmigration")),
                ("charge", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_adjustments", to="institutions.feecharge")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historical_fee_adjustments", to="institutions.school")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("batch", "charge"), name="unique_historical_migration_charge"),
                    models.CheckConstraint(condition=django.db.models.expressions.Q(("amount__gt", 0)), name="historical_adjustment_positive"),
                ],
            },
        ),
    ]
