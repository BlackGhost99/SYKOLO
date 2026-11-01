import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Global identity only. School permissions are membership-scoped in module 03."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class MFADevice(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="mfa_device")
    encrypted_secret = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_timestep = models.BigIntegerField(default=-1)


class MFARecoveryCode(models.Model):
    device = models.ForeignKey(MFADevice, on_delete=models.CASCADE, related_name="recovery_codes")
    digest = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["device", "digest"], name="unique_mfa_recovery_digest")
        ]


class AuthThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class AuthAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    event = models.CharField(max_length=48, db_index=True)
    ip_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
