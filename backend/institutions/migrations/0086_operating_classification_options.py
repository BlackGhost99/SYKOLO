"""B2 : classification optionnelle par école, sans modifier les écritures passées."""
import uuid
import django.db.models.deletion
from django.db import migrations, models


def protect_options(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        table = "institutions_operatingclassificationoption"
        cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
        for role in ("anon", "authenticated"):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if cursor.fetchone():
                cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0085_operating_expense_workflow")]

    operations = [
        migrations.CreateModel(
            name="OperatingClassificationOption",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4,
                                        editable=False, serialize=False)),
                ("kind", models.CharField(max_length=20, choices=[
                    ("pole", "Pôle d'activité"), ("cost_center", "Centre de coûts"),
                    ("accounting_nature", "Nature comptable"),
                ])),
                ("code", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=100)),
                ("activity_pole", models.CharField(max_length=20, blank=True,
                    default="", choices=[
                        ("", "Sans restriction"), ("school", "Scolarité"),
                        ("extraschool", "Extrascolaire"),
                        ("common", "Administration et charges communes"),
                        ("investment", "Investissements"),
                        ("cash_other", "Autres sorties de trésorerie"),
                    ])),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    to="institutions.school")),
            ],
        ),
        migrations.AddConstraint(
            model_name="operatingclassificationoption",
            constraint=models.UniqueConstraint(
                fields=("school", "kind", "code"),
                name="uniq_yem_out_classification_option",
            ),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="cost_center_ref",
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="center_expenses", to="institutions.operatingclassificationoption",
            ),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="accounting_nature_ref",
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="nature_expenses", to="institutions.operatingclassificationoption",
            ),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="activity_pole_label_snapshot",
            field=models.CharField(max_length=100, blank=True, default=""),
        ),
        migrations.RunPython(protect_options, migrations.RunPython.noop),
    ]
