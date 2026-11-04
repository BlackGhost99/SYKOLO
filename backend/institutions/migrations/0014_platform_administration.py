from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0013_guardian_account_links"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="SchoolAdminPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plan_name", models.CharField(default="Sans formule", max_length=80)),
                ("max_users", models.PositiveIntegerField(blank=True, null=True)),
                ("max_students", models.PositiveIntegerField(blank=True, null=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="admin_policy", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="PlatformAudit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event", models.CharField(db_index=True, max_length=48)),
                ("subject", models.CharField(max_length=180)),
                ("reason", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="institutions.school")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
