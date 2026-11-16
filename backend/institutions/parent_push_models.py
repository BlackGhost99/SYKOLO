"""Device registrations bound to an authenticated parent session."""
from django.conf import settings
from django.db import models
from django.contrib.sessions.models import Session


class ParentPushDevice(models.Model):
    token_digest = models.CharField(max_length=64, unique=True)
    encrypted_token = models.TextField()
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name="yem_parent_push")
    registered_at = models.DateTimeField(auto_now_add=True)
    refreshed_at = models.DateTimeField(auto_now=True)
