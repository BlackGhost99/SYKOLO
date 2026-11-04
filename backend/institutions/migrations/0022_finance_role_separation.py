from django.db import migrations


def separate_roles(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    School = apps.get_model("institutions", "School")
    alias = schema_editor.connection.alias
    for role in Role.objects.using(alias).filter(code__in=["direction", "comptabilite"]):
        permissions = set(role.permissions)
        if role.code == "direction":
            permissions -= {"school.finance.manage", "school.finance.receive", "school.finance.reverse", "school.finance.deposit"}
        else:
            permissions -= {"school.finance.manage", "school.finance.receive", "school.finance.deposit"}
            permissions.add("school.finance.reverse")
        permissions.add("school.finance.approve")
        role.permissions = sorted(permissions)
        role.revision += 1
        role.save(using=alias, update_fields=["permissions", "revision"])
    for school in School.objects.using(alias).all():
        for code, label, permissions in [
            ("econome", "Économe / Caissier", ["school.view", "school.students.read", "school.academic.read", "school.finance.read", "school.finance.receive", "school.finance.deposit"]),
            ("tarification", "Responsable des tarifs", ["school.view", "school.finance.read", "school.finance.manage"]),
        ]:
            Role.objects.using(alias).get_or_create(school=school, code=code, defaults={"label": label, "permissions": permissions})


class Migration(migrations.Migration):
    dependencies = [("institutions", "0021_financial_controls")]
    operations = [migrations.RunPython(separate_roles, migrations.RunPython.noop)]
