import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extensible identity foundation; sign-in and role policies arrive in module 02."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
