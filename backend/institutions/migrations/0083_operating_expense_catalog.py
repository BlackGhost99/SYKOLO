"""B2: expense-only catalog. Preserve all historical operations without guessing labels."""
import uuid
import django.db.models.deletion
from django.db import migrations, models


def protect_catalog(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        table = "institutions_operatingexpensecategory"
        cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
        for role in ("anon", "authenticated"):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if cursor.fetchone():
                cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0082_operating_expense_classification")]

    operations = [
        migrations.CreateModel(
            name="OperatingExpenseCategory",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4,
                                       editable=False, serialize=False)),
                ("code", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=100)),
                ("suggested_pole", models.CharField(blank=True, default="", max_length=20, choices=[
                    ("", "Aucun"), ("school", "Scolarité"), ("extraschool", "Extrascolaire"),
                    ("common", "Administration et charges communes"),
                    ("investment", "Investissements"), ("cash_other", "Autres sorties de trésorerie"),
                ])),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("parent", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT, related_name="subcategories",
                    to="institutions.operatingexpensecategory")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    to="institutions.school")),
            ],
        ),
        migrations.AddConstraint(
            model_name="operatingexpensecategory",
            constraint=models.UniqueConstraint(fields=("school", "code"),
                                               name="uniq_yem_out_category_code"),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="category_ref",
            field=models.ForeignKey(blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="classified_expenses",
                to="institutions.operatingexpensecategory"),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="subcategory_ref",
            field=models.ForeignKey(blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subclassified_expenses",
                to="institutions.operatingexpensecategory"),
        ),
        migrations.AddField(model_name="operatingexpense", name="category_label_snapshot",
            field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="operatingexpense", name="subcategory_label_snapshot",
            field=models.CharField(blank=True, default="", max_length=100)),
        migrations.RunPython(protect_catalog, migrations.RunPython.noop),
    ]
