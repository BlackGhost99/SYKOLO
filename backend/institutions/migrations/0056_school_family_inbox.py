from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0055_guardian_whatsapp_consent"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolFamilyNotification",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("destination", models.CharField(max_length=10, choices=[("school", "Établissement"), ("parent", "Parent")])),
                ("origin", models.CharField(max_length=10, choices=[("system", "YEM"), ("school", "Établissement"), ("parent", "Parent")])),
                ("message", models.CharField(max_length=700)),
                ("read_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, related_name="+", null=True, blank=True)),
                ("parent", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="yem_school_notifications")),
                ("school", models.ForeignKey(to="institutions.school", on_delete=django.db.models.deletion.PROTECT, related_name="family_notifications")),
                ("existing_request", models.ForeignKey(to="institutions.existingstudentlinkrequest", on_delete=django.db.models.deletion.PROTECT, related_name="notification_messages", null=True, blank=True)),
            ],
            options={"indexes": [
                models.Index(fields=["school", "destination", "-created_at"], name="yem_family_inbox_school"),
                models.Index(fields=["parent", "destination", "-created_at"], name="yem_family_inbox_parent"),
            ]},
        ),
    ]
