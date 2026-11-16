"""Device registrations bound to an authenticated parent session."""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.sessions.models import Session


class ParentPushDevice(models.Model):
    token_digest = models.CharField(max_length=64, unique=True)
    encrypted_token = models.TextField()
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name="yem_parent_push")
    registered_at = models.DateTimeField(auto_now_add=True)
    refreshed_at = models.DateTimeField(auto_now=True)


class ParentPushDelivery(models.Model):
    device = models.ForeignKey(ParentPushDevice, on_delete=models.CASCADE)
    notice = models.ForeignKey("institutions.SchoolFamilyNotification", on_delete=models.CASCADE)
    state = models.CharField(max_length=12, default="pending")
    attempts = models.PositiveSmallIntegerField(default=0)
    next_try = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["device", "notice"], name="unique_parent_push_delivery")]
        indexes = [models.Index(fields=["state", "next_try"], name="yem_push_due")]
