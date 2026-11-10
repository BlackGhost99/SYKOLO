"""Per-school academic-year payment gates and verifiable government support."""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            for name in ("institutions_admissionfinancepolicy", "institutions_governmentscholarship"):
                cursor.execute('ALTER TABLE "' + name + '" ENABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0041_school_demo_payment_config")]
    operations = [
        migrations.CreateModel(
            name="AdmissionFinancePolicy",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("scope_key", models.CharField(max_length=80)),
                ("require_payment", models.BooleanField(default=True)),
                ("allow_government_scholarship", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_finance_rules", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_finance_rules", to="institutions.academicyear")),
                ("level", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="admission_finance_rules", to="institutions.academiclevel")),
            ],
        ),
        migrations.AddConstraint(
            model_name="admissionfinancepolicy",
            constraint=models.UniqueConstraint(fields=["school", "scope_key"], name="unique_admission_finance_rule_scope"),
        ),
        migrations.CreateModel(
            name="GovernmentScholarship",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("coverage", models.CharField(max_length=16, default="all", choices=[("all", "Tous les frais"), ("admission", "Frais d'inscription seulement")])),
                ("official_reference", models.CharField(max_length=180)),
                ("active", models.BooleanField(default=True)),
                ("verified_at", models.DateTimeField(auto_now_add=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("application", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="government_scholarship", to="institutions.admissionapplication")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="government_scholarships", to="institutions.school")),
                ("verified_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="verified_government_scholarships", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(enable_rls, migrations.RunPython.noop),
    ]
