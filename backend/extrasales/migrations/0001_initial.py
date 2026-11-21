# Independent school-scoped receipts schema; does not share the B migrations.
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


def restrict_supabase_direct_clients(apps, schema_editor):
    """Direct Supabase anon/authenticated roles must never inspect money tables."""
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in (
            "extrasales_extrasale", "extrasales_extrasaleline", "extrasales_extrapayment",
        ):
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC')
            for role in ("anon", "authenticated"):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
                if cursor.fetchone():
                    cursor.execute(f'REVOKE ALL ON TABLE "{table}" FROM "{role}"')


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("institutions", "0081_gemini_daily_usage"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExtraSale",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reference", models.CharField(max_length=32)),
                ("buyer_label", models.CharField(max_length=120)),
                ("currency", models.CharField(max_length=3)),
                ("total", models.DecimalField(decimal_places=2, max_digits=12)),
                ("catalog_revision", models.PositiveIntegerField()),
                ("idempotency_key", models.CharField(max_length=80)),
                ("request_hash", models.CharField(max_length=64)),
                ("status", models.CharField(default="confirmed", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="extra_sales_created", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="extra_sales", to="institutions.school")),
                ("year", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="extra_sales", to="institutions.academicyear")),
            ],
        ),
        migrations.CreateModel(
            name="ExtraSaleLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("position", models.PositiveSmallIntegerField()),
                ("catalog_item_id", models.UUIDField()),
                ("code", models.CharField(max_length=30)),
                ("group", models.CharField(max_length=3)),
                ("kind", models.CharField(max_length=12)),
                ("label", models.CharField(max_length=120)),
                ("variant", models.CharField(blank=True, max_length=80)),
                ("unit", models.CharField(max_length=30)),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=12)),
                ("sale", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="lines", to="extrasales.extrasale")),
            ],
        ),
        migrations.CreateModel(
            name="ExtraPayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("currency", models.CharField(max_length=3)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("paid_on", models.DateField(default=django.utils.timezone.localdate)),
                ("method", models.CharField(choices=[
                    ("especes", "Espèces"), ("virement", "Virement bancaire"),
                ], max_length=24)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("evidence", models.CharField(default="manual_declared", max_length=24)),
                ("idempotency_key", models.CharField(max_length=80)),
                ("request_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("received_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="extra_manual_receipts_created", to=settings.AUTH_USER_MODEL)),
                ("sale", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="manual_receipts", to="extrasales.extrasale")),
                ("school", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="extra_manual_receipts", to="institutions.school")),
            ],
        ),
        migrations.AddConstraint(
            model_name="extrasale",
            constraint=models.UniqueConstraint(fields=("school", "reference"), name="extra_sale_school_reference"),
        ),
        migrations.AddConstraint(
            model_name="extrasale",
            constraint=models.UniqueConstraint(fields=("school", "idempotency_key"), name="extra_sale_school_idempotency"),
        ),
        migrations.AddConstraint(
            model_name="extrasale",
            constraint=models.CheckConstraint(condition=models.Q(("total__gt", 0)), name="extra_sale_positive_total"),
        ),
        migrations.AddConstraint(
            model_name="extrasaleline",
            constraint=models.UniqueConstraint(fields=("sale", "position"), name="extra_sale_line_position"),
        ),
        migrations.AddConstraint(
            model_name="extrasaleline",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="extra_sale_line_positive_qty"),
        ),
        migrations.AddConstraint(
            model_name="extrasaleline",
            constraint=models.CheckConstraint(condition=models.Q(("unit_price__gt", 0)), name="extra_sale_line_positive_unit"),
        ),
        migrations.AddConstraint(
            model_name="extrasaleline",
            constraint=models.CheckConstraint(condition=models.Q(("line_total__gt", 0)), name="extra_sale_line_positive_amount"),
        ),
        migrations.AddConstraint(
            model_name="extrapayment",
            constraint=models.UniqueConstraint(fields=("school", "idempotency_key"), name="extra_payment_school_idempotency"),
        ),
        migrations.AddConstraint(
            model_name="extrapayment",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="extra_payment_positive_amount"),
        ),
        migrations.RunPython(restrict_supabase_direct_clients, migrations.RunPython.noop),
    ]
