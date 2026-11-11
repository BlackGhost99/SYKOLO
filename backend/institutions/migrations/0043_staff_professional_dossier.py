"""Fiche professionnelle du personnel : données optionnelles et droits de consultation."""
from django.db import migrations, models
import django.db.models.deletion


def authorize_existing_standard_roles(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    alias = schema_editor.connection.alias
    for role in Role.objects.using(alias).filter(
        code__in=("direction", "principal", "proviseur", "secretariat")
    ).iterator():
        permissions = set(role.permissions or [])
        updated = set(permissions)
        # Ne pas réactiver un accès volontairement supprimé sur un rôle modifié.
        if role.code in ("direction", "principal", "proviseur"):
            if {"school.staff.read", "school.staff.manage"} <= permissions:
                updated.update(("school.staff.dossier.read", "school.staff.dossier.manage"))
        elif "school.staff.read" in permissions:
            updated.add("school.staff.dossier.read")
        if updated != permissions:
            role.permissions = sorted(updated)
            role.revision += 1
            role.save(update_fields=("permissions", "revision"))


class Migration(migrations.Migration):
    dependencies = [("institutions", "0042_admission_finance_scholarship")]

    operations = [
        migrations.CreateModel(
            name="StaffProfessionalDossier",
            fields=[
                ("staff", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    primary_key=True, related_name="professional_dossier",
                    serialize=False, to="institutions.staffrecord",
                )),
                ("qualification", models.CharField(blank=True, max_length=180)),
                ("specialty", models.CharField(blank=True, max_length=180)),
                ("employment_status", models.CharField(blank=True, max_length=100)),
                ("workload", models.CharField(blank=True, max_length=100)),
                ("professional_email", models.EmailField(blank=True, max_length=254)),
                ("professional_phone", models.CharField(blank=True, max_length=45)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(authorize_existing_standard_roles, migrations.RunPython.noop),
    ]
