"""M3.4 — school-scoped operating budgets, suppliers, expenses, declared payments."""
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def private_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in (
            "institutions_operatingsupplier", "institutions_operatingbudget",
            "institutions_operatingexpense", "institutions_operatingexpensepayment",
        ):
            cursor.execute(f'ALTER TABLE "public"."{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
            for (role,) in cursor.fetchall():
                cursor.execute(f'REVOKE ALL PRIVILEGES ON TABLE "public"."{table}" FROM "{role}"')


def standard_permissions(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    alias = schema_editor.connection.alias
    for role in Role.objects.using(alias).filter(
        code__in=("direction", "comptabilite", "econome")
    ).iterator():
        old = set(role.permissions or [])
        granted = set()
        if role.code == "direction" and {"school.staff.read", "school.finance.approve"} <= old:
            granted = {"school.operating.read", "school.operating.approve"}
        elif role.code == "comptabilite" and {"school.finance.read", "school.finance.approve"} <= old:
            granted = {"school.operating.read", "school.operating.manage", "school.operating.reverse"}
        elif role.code == "econome" and {"school.finance.read", "school.finance.receive"} <= old:
            granted = {"school.operating.read", "school.operating.pay"}
        if granted - old:
            role.permissions = sorted(old | granted)
            role.revision += 1
            role.save(update_fields=("permissions", "revision"))


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0051_payroll_ledger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="OperatingSupplier",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("contact", models.CharField(max_length=160, blank=True)),
                ("phone", models.CharField(max_length=50, blank=True)),
                ("email", models.EmailField(blank=True)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name="OperatingBudget",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("category", models.CharField(max_length=100)),
                ("currency", models.CharField(max_length=3, default="XAF")),
                ("ceiling", models.DecimalField(max_digits=12, decimal_places=2)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("approved_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT)),
                ("year", models.ForeignKey(to="institutions.academicyear", on_delete=django.db.models.deletion.PROTECT)),
                ("proposed_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="+")),
                ("approved_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="+", null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="OperatingExpense",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("label", models.CharField(max_length=200)),
                ("amount", models.DecimalField(max_digits=12, decimal_places=2)),
                ("expense_on", models.DateField()),
                ("invoice_reference", models.CharField(max_length=120)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("approved_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT)),
                ("year", models.ForeignKey(to="institutions.academicyear", on_delete=django.db.models.deletion.PROTECT)),
                ("budget", models.ForeignKey(to="institutions.operatingbudget", on_delete=django.db.models.deletion.PROTECT, related_name="expenses")),
                ("supplier", models.ForeignKey(to="institutions.operatingsupplier", on_delete=django.db.models.deletion.PROTECT, related_name="expenses")),
                ("prepared_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="+")),
                ("approved_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="+", null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="OperatingExpensePayment",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("amount", models.DecimalField(max_digits=12, decimal_places=2)),
                ("method", models.CharField(max_length=20)),
                ("reference", models.CharField(max_length=120)),
                ("paid_on", models.DateField()),
                ("idempotency_key", models.UUIDField()),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("voided_at", models.DateTimeField(null=True, blank=True)),
                ("void_reason", models.CharField(max_length=240, blank=True)),
                ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT)),
                ("expense", models.ForeignKey(to="institutions.operatingexpense", on_delete=django.db.models.deletion.PROTECT, related_name="payments")),
                ("recorded_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="+")),
                ("voided_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="+", null=True, blank=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="operatingbudget",
            constraint=models.UniqueConstraint(fields=("school", "year", "category", "currency"), name="uniq_yem_operating_budget"),
        ),
        migrations.AddConstraint(
            model_name="operatingbudget",
            constraint=models.CheckConstraint(condition=Q(ceiling__gt=0), name="yem_operating_budget_positive"),
        ),
        migrations.AddConstraint(
            model_name="operatingexpense",
            constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="yem_operating_expense_positive"),
        ),
        migrations.AddConstraint(
            model_name="operatingexpensepayment",
            constraint=models.UniqueConstraint(fields=("school", "idempotency_key"), name="uniq_yem_expense_payment_key"),
        ),
        migrations.AddConstraint(
            model_name="operatingexpensepayment",
            constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="yem_operating_payment_positive"),
        ),
        migrations.RunPython(private_tables, migrations.RunPython.noop),
        migrations.RunPython(standard_permissions, migrations.RunPython.noop),
    ]
