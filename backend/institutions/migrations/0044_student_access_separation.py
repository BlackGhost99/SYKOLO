"""Évolution non destructive des rôles historiques de YEM.

Les rôles d'une école sont personnalisables : les permissions existantes
non ciblées sont préservées. Aucun nouveau droit sensible n'est donné aux
comptes comptables, économes, enseignants ou rôles personnalisés.
"""
from django.db import migrations


def migrate_student_role_permissions(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    db = schema_editor.connection.alias
    management = {"direction", "principal", "proviseur", "secretariat"}
    financial = {"comptabilite", "econome"}
    for role in Role.objects.using(db).filter(
        code__in=[*management, *financial, "secretariat_pedagogique"]
    ).iterator():
        old = list(role.permissions or [])
        new = set(old)
        if role.code in financial and "school.students.manage" not in new:
            if "school.students.read" in new:
                new.remove("school.students.read")
                new.add("school.students.finance.read")
        elif role.code in management:
            if "school.students.read" in new:
                new.add("school.students.profile.read")
            if "school.students.manage" in new:
                new.add("school.students.admin.write")
            if {"school.students.read", "school.students.manage"} <= new:
                new.add("school.students.sensitive.read")
            if "school.finance.read" in new:
                new.add("school.students.finance.read")
        elif role.code == "secretariat_pedagogique" and "school.students.read" in new:
            new.add("school.students.profile.read")
        if new != set(old):
            role.permissions = sorted(new)
            role.revision += 1
            role.save(update_fields=["permissions", "revision"])


class Migration(migrations.Migration):
    dependencies = [("institutions", "0043_school_governance_mode")]
    operations = [
        migrations.RunPython(migrate_student_role_permissions, migrations.RunPython.noop)
    ]
