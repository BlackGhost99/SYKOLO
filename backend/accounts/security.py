"""Authentication security helpers. No school data is authorized by this module."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AuthAudit, AuthThrottle, MFADevice, MFARecoveryCode


def fingerprint(value):
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def client_identity(request):
    # REMOTE_ADDR is supplied by the trusted WSGI server, never a client-controlled XFF.
    return str(request.META.get("REMOTE_ADDR") or "unknown")[:128]


def audit(request, event, actor=None):
    AuthAudit.objects.create(
        event=event, actor=actor, ip_hash=fingerprint(client_identity(request))
    )


def throttle_key(request, purpose, identifier):
    return fingerprint(f"{purpose}:{client_identity(request)}:{identifier.strip().casefold()[:160]}")


def is_locked(key):
    now = timezone.now()
    with transaction.atomic():
        obj = AuthThrottle.objects.select_for_update().filter(pk=key).first()
        if not obj:
            return False
        if obj.updated_at < now - timedelta(minutes=15):
            obj.delete()
            return False
        return bool(obj.locked_until and obj.locked_until > now)


def failure(key, limit=5):
    now = timezone.now()
    with transaction.atomic():
        obj, _ = AuthThrottle.objects.select_for_update().get_or_create(key=key)
        if obj.updated_at < now - timedelta(minutes=15):
            obj.failures = 0
            obj.locked_until = None
        obj.failures = min(65535, obj.failures + 1)
        if obj.failures >= limit:
            obj.locked_until = now + timedelta(minutes=15)
        obj.save()


def clear_throttle(key):
    AuthThrottle.objects.filter(pk=key).delete()


def fernet():
    # Independent, high-entropy deployment secret; do not rotate without re-enrolling MFA.
    digest = hashlib.sha256(("yem/totp/v1:" + settings.MFA_ENCRYPTION_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret):
    return fernet().encrypt(secret.encode()).decode()


def decrypt_secret(secret):
    return fernet().decrypt(secret.encode()).decode()


def new_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().strip("=")


def totp_at(secret, timestep):
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(secret + padding, casefold=True)
    mac = hmac.new(key, struct.pack(">Q", timestep), hashlib.sha1).digest()
    offset = mac[-1] & 15
    n = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{n % 1000000:06d}"


def recovery_digest(code):
    normalized = code.strip().replace("-", "").upper()
    return fingerprint("recovery:" + normalized)


def new_recovery_codes(device):
    codes = [secrets.token_hex(8).upper() for _ in range(8)]
    MFARecoveryCode.objects.bulk_create(
        [MFARecoveryCode(device=device, digest=recovery_digest(c)) for c in codes]
    )
    return codes


def verify_factor(user, supplied, *, require_confirmed=True):
    if not isinstance(supplied, str) or len(supplied) > 64:
        return False
    with transaction.atomic():
        device = MFADevice.objects.select_for_update().filter(user=user).first()
        if not device or (require_confirmed and not device.confirmed_at):
            return False
        if not device.confirmed_at and device.created_at < timezone.now() - timedelta(minutes=10):
            return False
        if len(supplied) == 6 and supplied.isascii() and supplied.isdecimal():
            step = int(time.time()) // 30
            try:
                secret = decrypt_secret(device.encrypted_secret)
            except Exception:
                return False
            for timestep in (step - 1, step, step + 1):
                if timestep > device.last_timestep and hmac.compare_digest(totp_at(secret, timestep), supplied):
                    device.last_timestep = timestep
                    device.save(update_fields=["last_timestep"])
                    return True
        if require_confirmed and device.confirmed_at:
            digest = recovery_digest(supplied)
            deleted, _ = MFARecoveryCode.objects.filter(device=device, digest=digest).delete()
            return bool(deleted)
    return False
