"""Physical returns only: money/refunds remain a separate controlled workflow."""
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def secure_return_table(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        table = "extrasales_extraproductreturn"
        cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        cursor.execute(f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC')
        for role in ("anon", "authenticated"):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if cursor.fetchone():
                cursor.execute(f'REVOKE ALL ON TABLE "{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [
        ("extrasales", "0002_stock"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name="ExtraProductReturn", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("quantity", models.PositiveIntegerField()),
            ("reason", models.CharField(max_length=240)),
            ("operation_key", models.CharField(max_length=120)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ("sale_line", models.ForeignKey(to="extrasales.extrasaleline", related_name="product_returns", on_delete=django.db.models.deletion.PROTECT)),
            ("school", models.ForeignKey(to="institutions.school", related_name="extra_product_returns", on_delete=django.db.models.deletion.PROTECT)),
            ("stock", models.ForeignKey(to="extrasales.extrastock", related_name="product_returns", on_delete=django.db.models.deletion.PROTECT)),
        ]),
        migrations.AddConstraint(model_name="extraproductreturn", constraint=models.UniqueConstraint(fields=("school", "operation_key"), name="extra_return_school_operation")),
        migrations.AddConstraint(model_name="extraproductreturn", constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="extra_return_positive_quantity")),
        migrations.RunPython(secure_return_table, migrations.RunPython.noop),
    ]
