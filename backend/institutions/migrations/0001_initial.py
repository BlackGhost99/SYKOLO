import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("accounts", "0002_auth_security"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="OrganizationMember",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(default="founder", max_length=32)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="institutions.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="School",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("short_name", models.CharField(blank=True, max_length=60)),
                ("primary_color", models.CharField(default="#1B664C", max_length=7)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="schools", to="institutions.organization")),
            ],
        ),
        migrations.CreateModel(
            name="SchoolRole",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=48)),
                ("label", models.CharField(max_length=100)),
                ("permissions", models.JSONField(default=list)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="roles", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="SchoolMember",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("active", models.BooleanField(default=True)),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="institutions.schoolrole")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="institutions.school")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="SchoolSetting",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scope_key", models.CharField(max_length=260)),
                ("scope", models.JSONField(default=dict)),
                ("values", models.JSONField(default=dict)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="settings", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="SchoolAudit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event", models.CharField(max_length=48)),
                ("subject", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_events", to="institutions.school")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint("organizationmember", models.UniqueConstraint(fields=("organization", "user"), name="unique_org_membership")),
        migrations.AddConstraint("schoolrole", models.UniqueConstraint(fields=("school", "code"), name="unique_school_role")),
        migrations.AddConstraint("schoolmember", models.UniqueConstraint(fields=("school", "user"), name="unique_school_membership")),
        migrations.AddConstraint("schoolsetting", models.UniqueConstraint(fields=("school", "scope_key"), name="unique_school_setting_scope")),
    ]
