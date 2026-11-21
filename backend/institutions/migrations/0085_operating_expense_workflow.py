"""B3b — additive expense authorization workflow, preserving legacy approvals."""
import uuid
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def backfill_approved(apps, schema_editor):
    Expense = apps.get_model("institutions", "OperatingExpense")
    # Existing accepted expenses retain their approved status, commitment and payments.
    Expense.objects.filter(approved_at__isnull=False).update(workflow_state="approved")


def protect_decisions(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        table = "institutions_operatingexpensedecision"
        cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
        for role in ("anon", "authenticated"):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if cursor.fetchone():
                cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0084_operating_expense_beneficiaries"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="operatingexpense", name="workflow_state",
            field=models.CharField(max_length=12, default="draft", choices=[
                ("draft", "Brouillon"), ("submitted", "Soumise"),
                ("rejected", "Refusée"), ("approved", "Approuvée"),
            ]),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="submitted_by",
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=django.db.models.deletion.PROTECT,
                                    related_name="+"),
        ),
        migrations.AddField(
            model_name="operatingexpense", name="submitted_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.CreateModel(
            name="OperatingExpenseDecision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                       primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=16, choices=[
                    ("submitted", "Soumise"), ("rejected", "Refusée"),
                    ("approved", "Approuvée"), ("revised", "Révisée"),
                ])),
                ("revision", models.PositiveIntegerField()),
                ("reason", models.CharField(max_length=240, blank=True, default="")),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.PROTECT, related_name="+")),
                ("expense", models.ForeignKey(to="institutions.operatingexpense",
                    on_delete=django.db.models.deletion.PROTECT, related_name="workflow_decisions")),
                ("school", models.ForeignKey(to="institutions.school",
                    on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.RunPython(backfill_approved, migrations.RunPython.noop),
        migrations.RunPython(protect_decisions, migrations.RunPython.noop),
    ]
