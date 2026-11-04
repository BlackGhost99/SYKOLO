"""Fonctions multiples par école et cycle ; migration des droits de lecture/gestion."""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def grant_existing_management_permissions(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    for role in Role.objects.all().iterator():
        permissions = set(role.permissions or [])
        additions = set()
        if role.code in ("direction", "proprietaire") and "school.staff.manage" in permissions:
            additions = {"school.organization.read", "school.organization.manage"}
        elif role.code == "secretariat" and "school.staff.read" in permissions:
            additions = {"school.organization.read"}
        if additions - permissions:
            role.permissions = sorted(permissions | additions)
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0017_parent_discovery"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="SchoolAppointment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("function_code", models.SlugField(max_length=48)),
                ("cycle_code", models.CharField(blank=True, default="", max_length=32)),
                ("starts_on", models.DateField(blank=True, null=True)),
                ("ends_on", models.DateField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("appointed_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL
                )),
                ("school", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="appointments", to="institutions.school"
                )),
                ("staff", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="appointments", to="institutions.staffrecord"
                )),
            ],
            options={"ordering": ("function_code", "cycle_code", "staff__last_name", "pk")},
        ),
        migrations.AddConstraint(
            model_name="schoolappointment",
            constraint=models.UniqueConstraint(
                fields=("school", "staff", "function_code", "cycle_code"),
                name="unique_school_function_appointment",
            ),
        ),
        migrations.RunPython(grant_existing_management_permissions, migrations.RunPython.noop),
    ]
