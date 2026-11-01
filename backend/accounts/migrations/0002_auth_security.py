import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="AuthThrottle",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("failures", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="AuthAudit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event", models.CharField(db_index=True, max_length=48)),
                ("ip_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="MFADevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("encrypted_secret", models.CharField(max_length=512)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("last_timestep", models.BigIntegerField(default=-1)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="mfa_device", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="MFARecoveryCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("digest", models.CharField(max_length=64)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recovery_codes", to="accounts.mfadevice")),
            ],
        ),
        migrations.AddConstraint(
            model_name="mfarecoverycode",
            constraint=models.UniqueConstraint(fields=("device", "digest"), name="unique_mfa_recovery_digest"),
        ),
    ]
