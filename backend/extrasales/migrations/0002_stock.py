"""A6c: isolated inventory, independent of institutions 0082-0085."""
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def protect_stock_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in ("extrasales_extrastock", "extrasales_extrastockmovement"):
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC')
            for role in ("anon", "authenticated"):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
                if cursor.fetchone():
                    cursor.execute(f'REVOKE ALL ON TABLE "{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [
        ("extrasales", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name="ExtraStock", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("catalog_item_id", models.UUIDField()),
            ("quantity", models.PositiveIntegerField(default=0)),
            ("revision", models.PositiveIntegerField(default=0)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT, related_name="extra_stock_items")),
        ]),
        migrations.CreateModel(name="ExtraStockMovement", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("delta", models.IntegerField()),
            ("quantity_after", models.PositiveIntegerField()),
            ("movement_type", models.CharField(max_length=24)),
            ("reason", models.CharField(max_length=240)),
            ("operation_key", models.CharField(max_length=120)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ("sale", models.ForeignKey(to="extrasales.extrasale", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements")),
            ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT, related_name="extra_stock_movements")),
            ("stock", models.ForeignKey(to="extrasales.extrastock", on_delete=django.db.models.deletion.PROTECT, related_name="movements")),
        ]),
        migrations.AddConstraint(model_name="extrastock", constraint=models.UniqueConstraint(fields=("school", "catalog_item_id"), name="extra_stock_school_product")),
        migrations.AddConstraint(model_name="extrastock", constraint=models.CheckConstraint(condition=models.Q(quantity__gte=0), name="extra_stock_nonnegative")),
        migrations.AddConstraint(model_name="extrastockmovement", constraint=models.UniqueConstraint(fields=("school", "operation_key"), name="extra_stock_school_operation")),
        migrations.AddConstraint(model_name="extrastockmovement", constraint=models.CheckConstraint(condition=~models.Q(delta=0), name="extra_stock_delta_nonzero")),
        migrations.RunPython(protect_stock_tables, migrations.RunPython.noop),
    ]
