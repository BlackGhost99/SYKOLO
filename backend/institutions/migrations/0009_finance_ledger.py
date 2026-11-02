import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


def grant_finance_permissions(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    additions = {
        "direction": ["school.finance.read", "school.finance.manage", "school.finance.receive", "school.finance.reverse"],
        "comptabilite": ["school.students.read", "school.academic.read",
                        "school.finance.read", "school.finance.manage", "school.finance.receive"],
    }
    # Never rewrite a custom role (revision > 1).
    for role in Role.objects.filter(code__in=additions, revision=1).iterator():
        perms = list(role.permissions)
        extras = [p for p in additions[role.code] if p not in perms]
        if extras:
            role.permissions = perms + extras
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0008_deliberations"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FeeSchedule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scope_key", models.CharField(blank=True, max_length=36)),
                ("code", models.SlugField(max_length=48)),
                ("label", models.CharField(max_length=160)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_schedules", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_schedules", to="institutions.academicyear")),
                ("classroom", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fee_schedules", to="institutions.academicclass")),
            ],
        ),
        migrations.CreateModel(
            name="FeeCharge",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_charges", to="institutions.school")),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_charges", to="institutions.enrollment")),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="charges", to="institutions.feeschedule")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="FeePayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("idempotency_key", models.UUIDField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("method", models.SlugField(max_length=48)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("paid_on", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_payments", to="institutions.school")),
                ("charge", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="institutions.feecharge")),
                ("recorded_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="FeePaymentVoid",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reason", models.TextField(max_length=1000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_payment_voids", to="institutions.school")),
                ("payment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="void", to="institutions.feepayment")),
                ("approved_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="feeschedule",
            constraint=models.UniqueConstraint(fields=("school", "year", "scope_key", "code"), name="unique_fee_schedule_per_scope"),
        ),
        migrations.AddConstraint(
            model_name="feeschedule",
            constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="fee_schedule_amount_positive"),
        ),
        migrations.AddConstraint(
            model_name="feecharge",
            constraint=models.UniqueConstraint(fields=("school", "enrollment", "schedule"), name="unique_enrollment_fee_charge"),
        ),
        migrations.AddConstraint(
            model_name="feecharge",
            constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="fee_charge_amount_positive"),
        ),
        migrations.AddConstraint(
            model_name="feepayment",
            constraint=models.UniqueConstraint(fields=("school", "idempotency_key"), name="unique_school_payment_idempotency"),
        ),
        migrations.AddConstraint(
            model_name="feepayment",
            constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="fee_payment_amount_positive"),
        ),
        migrations.RunPython(grant_finance_permissions, migrations.RunPython.noop),
    ]
