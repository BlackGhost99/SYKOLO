"""B3: demandes scolaires sans effet sur le grand livre et permissions limitées."""
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def private_request_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in (
            "institutions_operatingschoolrequest",
            "institutions_operatingschoolrequestevent",
        ):
            cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
            for role in ("anon", "authenticated"):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
                if cursor.fetchone():
                    cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"')


def grant_existing_requesters(apps, schema_editor):
    SchoolRole = apps.get_model("institutions", "SchoolRole")
    for role in SchoolRole.objects.filter(code__in=("enseignant", "secretariat", "direction")):
        current = set(role.permissions or [])
        if "school.operating.request" not in current:
            role.permissions = sorted(current | {"school.operating.request"})
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0086_operating_classification_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OperatingSchoolRequest",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4,
                                        editable=False, serialize=False)),
                ("requester_function", models.CharField(max_length=120)),
                ("service", models.CharField(max_length=120)),
                ("reason", models.CharField(max_length=600)),
                ("category_snapshot", models.CharField(max_length=100)),
                ("subcategory_snapshot", models.CharField(max_length=100, blank=True, default="")),
                ("cost_center_snapshot", models.CharField(max_length=100, blank=True, default="")),
                ("description", models.CharField(max_length=200)),
                ("quantity", models.DecimalField(max_digits=12, decimal_places=2)),
                ("estimated_unit_price", models.DecimalField(max_digits=12, decimal_places=2,
                                                               null=True, blank=True)),
                ("estimated_amount", models.DecimalField(max_digits=12, decimal_places=2)),
                ("currency", models.CharField(max_length=3, default="XAF")),
                ("beneficiary_name", models.CharField(max_length=180)),
                ("urgency", models.CharField(max_length=12, choices=[
                    ("normal", "Normale"), ("high", "Prioritaire"), ("critical", "Urgente"),
                ], default="normal")),
                ("desired_on", models.DateField()),
                ("supporting_reference", models.CharField(max_length=240, blank=True, default="")),
                ("status", models.CharField(max_length=12, choices=[
                    ("draft", "Brouillon"), ("submitted", "Soumise"),
                    ("in_review", "En examen"), ("approved", "Validée pour instruction budgétaire"),
                    ("rejected", "Refusée"), ("cancelled", "Annulée"),
                ], default="draft")),
                ("revision", models.PositiveIntegerField(default=1)),
                ("idempotency_key", models.UUIDField()),
                ("submitted_at", models.DateTimeField(null=True, blank=True)),
                ("reviewed_at", models.DateTimeField(null=True, blank=True)),
                ("decided_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                          to="institutions.academicyear")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to=settings.AUTH_USER_MODEL)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="institutions.operatingexpensecategory")),
                ("subcategory", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", null=True, blank=True,
                    to="institutions.operatingexpensecategory")),
                ("cost_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", null=True, blank=True,
                    to="institutions.operatingclassificationoption")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", null=True, blank=True,
                    to="institutions.operatingsupplier")),
                ("reviewed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", null=True, blank=True,
                    to=settings.AUTH_USER_MODEL)),
                ("decided_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", null=True, blank=True,
                    to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="operatingschoolrequest",
            constraint=models.UniqueConstraint(
                fields=("school", "idempotency_key"), name="uniq_yem_school_request_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="operatingschoolrequest",
            constraint=models.CheckConstraint(
                condition=Q(quantity__gt=0), name="yem_school_request_quantity_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="operatingschoolrequest",
            constraint=models.CheckConstraint(
                condition=Q(estimated_amount__gt=0), name="yem_school_request_amount_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="operatingschoolrequest",
            constraint=models.CheckConstraint(
                condition=Q(estimated_unit_price__isnull=True) | Q(estimated_unit_price__gt=0),
                name="yem_school_request_unit_price_positive"
            ),
        ),
        migrations.CreateModel(
            name="OperatingSchoolRequestEvent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4,
                                        editable=False, serialize=False)),
                ("action", models.CharField(max_length=20, choices=[
                    ("submitted", "Soumise"), ("in_review", "En examen"),
                    ("approved", "Validée"), ("rejected", "Refusée"),
                    ("revised", "Révisée"), ("cancelled", "Annulée"),
                ])),
                ("revision", models.PositiveIntegerField()),
                ("reason", models.CharField(max_length=500, blank=True, default="")),
                ("happened_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            to="institutions.school")),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="events", to="institutions.operatingschoolrequest")),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(private_request_tables, migrations.RunPython.noop),
        migrations.RunPython(grant_existing_requesters, migrations.RunPython.noop),
    ]
