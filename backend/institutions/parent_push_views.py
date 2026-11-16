"""Private opt-in FCM registration. No provider call in an HTTP request."""
import base64
import hashlib
import re

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.views import authorized
from .parent_push_models import ParentPushDevice
from .views import parse_body


TOKEN = re.compile(r"[A-Za-z0-9_:\-.]{20,4096}\Z")


def push_cipher():
    key = settings.YEM_PARENT_PUSH_KEY
    if len(key) < 32:
        raise ValueError("Push non configuré.")
    digest = hashlib.sha256(("yem-parent-push-v1:" + key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


@never_cache
@require_http_methods(["POST", "DELETE"])
@authorized
def push_device(request):
    if request.session.get("login_scope") != "parent" or request.user.is_superuser or request.session.get("school_id"):
        return JsonResponse({"error": "Session parent requise."}, status=403)
    session_key = request.session.session_key
    if request.method == "DELETE":
        ParentPushDevice.objects.filter(parent=request.user, session_id=session_key).delete()
        return JsonResponse({"registered": False})
    if not settings.YEM_PARENT_PUSH_ENABLED or len(settings.YEM_PARENT_PUSH_KEY) < 32:
        return JsonResponse({"error": "Notifications push non activées."}, status=503)
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) != {"token"} or not isinstance(data["token"], str) or not TOKEN.fullmatch(data["token"]):
        return JsonResponse({"error": "Jeton d’appareil invalide."}, status=422)
    token = data["token"]
    digest = hashlib.sha256(token.encode()).hexdigest()
    encrypted = push_cipher().encrypt(token.encode()).decode()
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk, is_active=True)
            if not Session.objects.select_for_update().filter(session_key=session_key, expire_date__gt=timezone.now()).exists():
                return JsonResponse({"error": "Session expirée."}, status=401)
            existing = ParentPushDevice.objects.select_for_update().filter(token_digest=digest).first()
            if existing and existing.parent_id != request.user.pk:
                # A different account must explicitly revoke the old registration first.
                # Avoid allowing a stolen token to displace another family.
                return JsonResponse({"error": "Appareil déjà associé à un autre compte."}, status=409)
            current = ParentPushDevice.objects.filter(session_id=session_key, parent=request.user).first()
            if existing and current and existing.pk == current.pk:
                existing.encrypted_token = encrypted
                existing.save(update_fields=["encrypted_token", "refreshed_at"])
                return JsonResponse({"registered": True})
            live = ParentPushDevice.objects.filter(parent=request.user, session__expire_date__gt=timezone.now()).exclude(session_id=session_key)
            if existing:
                live = live.exclude(pk=existing.pk)
            if live.count() >= 10:
                return JsonResponse({"error": "Limite d'appareils atteinte."}, status=409)
            if current:
                current.delete()
            if existing:
                existing.delete()
            ParentPushDevice.objects.create(parent=request.user, session_id=session_key, token_digest=digest, encrypted_token=encrypted)
    except (IntegrityError, get_user_model().DoesNotExist):
        return JsonResponse({"error": "Session ou appareil modifié. Réessayez."}, status=409)
    return JsonResponse({"registered": True}, status=201)
