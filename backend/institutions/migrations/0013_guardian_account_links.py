import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def grant_management(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    for role in Role.objects.filter(code="direction", revision=1).iterator():
        if "school.parents.manage" not in role.permissions:
            role.permissions = list(role.permissions) + ["school.parents.manage"]
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0012_admissions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="GuardianAccountLink",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("verified_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="guardian_account_links", to="institutions.school")),
                ("guardian", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="account_links", to="institutions.studentguardian")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="yem_guardian_links", to=settings.AUTH_USER_MODEL)),
                ("verified_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="guardianaccountlink",
            constraint=models.UniqueConstraint(fields=("school", "guardian", "user"), name="unique_school_guardian_account"),
        ),
        migrations.RunPython(grant_management, migrations.RunPython.noop),
    ]
