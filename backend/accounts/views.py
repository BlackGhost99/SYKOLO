"""Session-based same-origin authentication. No public registration."""
import json
import logging
from functools import wraps
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import JsonResponse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.db import transaction

from .models import AuthAudit, MFADevice, MFARecoveryCode
from .qr import make_qr_data_uri
from .security import (
    audit, clear_throttle, encrypt_secret, failure, is_locked, new_recovery_codes,
    new_totp_secret, throttle_key, verify_factor,
)

log = logging.getLogger(__name__)


def payload(request):
    if request.content_type != "application/json":
        return None, JsonResponse({"error": "JSON requis."}, status=415)
    if len(request.body) > 4096:
        return None, JsonResponse({"error": "Requête trop volumineuse."}, status=413)
    try:
        data = json.loads(request.body)
    except (UnicodeDecodeError, ValueError):
        return None, JsonResponse({"error": "JSON invalide."}, status=400)
    if not isinstance(data, dict):
        return None, JsonResponse({"error": "Objet JSON requis."}, status=400)
    return data, None


def authorized(fn):
    @wraps(fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            return JsonResponse({"error": "Authentification requise."}, status=401)
        return fn(request, *args, **kwargs)
    return wrapper


def public_user(user):
    return {
        "id": str(user.pk), "username": user.get_username(),
        "first_name": user.first_name, "last_name": user.last_name,
        "is_platform_admin": bool(user.is_superuser),
    }


@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"csrf": "ready"})


@require_GET
def me(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({"authenticated": False})
    device = MFADevice.objects.filter(user=request.user, confirmed_at__isnull=False).first()
    return JsonResponse({
        "authenticated": True,
        "user": {**public_user(request.user), "username": request.session.get("school_username", request.user.username)},
        "school_id": request.session.get("school_id"),
        "login_scope": request.session.get("login_scope"),
        "mfa_enabled": bool(device),
    })


@require_POST
def sign_in(request):
    data, error = payload(request)
    if error is not None:
        return error
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 150 or len(password) > 1024:
        return JsonResponse({"error": "Identifiants invalides."}, status=401)
    scope = data.get("scope", "parent")
    school_code = data.get("school_code", "")
    if scope not in {"school", "platform", "parent"} or not isinstance(school_code, str):
        return JsonResponse({"error": "Accès invalide."}, status=401)
    if scope == "school":
        try:
            from uuid import UUID
            school_code = str(UUID(school_code))
        except ValueError:
            school_code = "00000000-0000-0000-0000-000000000000"
    else:
        school_code = ""
    key = throttle_key(request, "login", scope + ":" + school_code + ":" + username)
    if is_locked(key):
        audit(request, "login_throttled")
        return JsonResponse({"error": "Connexion temporairement indisponible."}, status=429)
    from institutions.models import SchoolLogin, SchoolMember, OrganizationMember
    from institutions.services import school_access, effective_permissions
    school = None
    if scope == "school":
        try:
            identity = SchoolLogin.objects.select_related("user", "school").filter(
                school_id=school_code, username=username, school__is_active=True).first()
        except (ValueError, ValidationError):
            identity = None
        user = authenticate(request, username=identity.user.username if identity else "__invalid_school__", password=password)
        if not identity or not user or user.is_superuser or not school_access(user, identity.school_id):
            user = None
        else:
            school = identity.school
    else:
        user = authenticate(request, username=username, password=password)
        if user and ((scope == "platform" and not user.is_superuser) or
                     (scope == "parent" and (user.is_superuser or
                      any(effective_permissions(user, m.school) - {"school.view"} for m in SchoolMember.objects.select_related("school").filter(user=user, active=True)) or
                      OrganizationMember.objects.filter(user=user).exists()))):
            user = None
    if user is None or not user.is_active:
        failure(key)
        audit(request, "login_failed")
        return JsonResponse({"error": "Identifiants invalides."}, status=401)
    device = MFADevice.objects.filter(user=user, confirmed_at__isnull=False).first()
    if device:
        factor = data.get("code")
        if not isinstance(factor, str) or not factor.strip():
            return JsonResponse({"error": "Code de vérification requis.", "mfa_required": True}, status=401)
        if not verify_factor(user, factor):
            failure(key)
            audit(request, "mfa_failed", user)
            return JsonResponse({"error": "Code de vérification invalide.", "mfa_required": True}, status=401)
    request.session.flush()
    login(request, user)
    request.session["login_scope"] = scope
    if school:
        request.session["school_id"] = str(school.pk)
        request.session["school_username"] = username
    request.session["mfa_verified"] = bool(device)
    request.session.set_expiry(8 * 3600)
    clear_throttle(key)
    audit(request, "login_success", user)
    return JsonResponse({"authenticated": True, "user": public_user(user)})


@require_POST
@authorized
def sign_out(request):
    user = request.user
    audit(request, "logout", user)
    logout(request)
    return JsonResponse({"authenticated": False})


@require_POST
@authorized
def change_password(request):
    data, error = payload(request)
    if error is not None:
        return error
    current, new = data.get("current_password"), data.get("new_password")
    if not isinstance(current, str) or not request.user.check_password(current):
        return JsonResponse({"error": "Mot de passe actuel incorrect."}, status=400)
    try:
        if not isinstance(new, str):
            raise ValidationError("Mot de passe invalide.")
        validate_password(new, user=request.user)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=422)
    request.user.set_password(new)
    request.user.save(update_fields=["password"])
    update_session_auth_hash(request, request.user)
    audit(request, "password_changed", request.user)
    return JsonResponse({"changed": True})


@require_POST
def password_reset_request(request):
    data, error = payload(request)
    if error is not None:
        return error
    if not settings.PASSWORD_RESET_ENABLED:
        return JsonResponse({"error": "Récupération indisponible : messagerie non configurée."}, status=503)
    email = data.get("email")
    if not isinstance(email, str) or len(email) > 254 or "@" not in email:
        return JsonResponse({"error": "Adresse email invalide."}, status=400)
    generic = {"message": "Si un compte correspond, un lien sera envoyé."}
    key = throttle_key(request, "reset", email)
    if is_locked(key):
        return JsonResponse(generic)
    failure(key, limit=3)
    users = get_user_model().objects.filter(email__iexact=email.strip(), is_active=True).order_by("pk")[:3]
    for user in users:
        if not user.has_usable_password():
            continue
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{settings.AUTH_PUBLIC_BASE_URL.rstrip('/')}/#/reset?uid={quote(uid)}&token={quote(token)}"
        try:
            send_mail(
                "YEM — Réinitialisation du mot de passe",
                "Pour réinitialiser votre mot de passe, ouvrez ce lien (valable 30 minutes) :\n" + link,
                settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
            )
            audit(request, "reset_requested", user)
        except Exception:
            log.exception("Password reset email delivery failed")
    return JsonResponse(generic)


@require_POST
def password_reset_confirm(request):
    data, error = payload(request)
    if error is not None:
        return error
    uid, token, password = data.get("uid"), data.get("token"), data.get("password")
    if not all(isinstance(x, str) for x in [uid, token, password]) or len(token) > 128 or len(uid) > 128:
        return JsonResponse({"error": "Lien invalide ou expiré."}, status=400)
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = get_user_model().objects.get(pk=pk, is_active=True)
    except (ValueError, TypeError, OverflowError, get_user_model().DoesNotExist):
        return JsonResponse({"error": "Lien invalide ou expiré."}, status=400)
    if not default_token_generator.check_token(user, token):
        return JsonResponse({"error": "Lien invalide ou expiré."}, status=400)
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=422)
    user.set_password(password)
    user.save(update_fields=["password"])
    audit(request, "password_reset_confirmed", user)
    return JsonResponse({"changed": True})


@require_POST
@authorized
def mfa_begin(request):
    data, error = payload(request)
    if error is not None:
        return error
    password = data.get("password")
    if not isinstance(password, str) or not request.user.check_password(password):
        return JsonResponse({"error": "Mot de passe incorrect."}, status=403)
    if MFADevice.objects.filter(user=request.user, confirmed_at__isnull=False).exists():
        return JsonResponse({"error": "Double authentification déjà activée."}, status=409)
    secret = new_totp_secret()
    MFADevice.objects.update_or_create(
        user=request.user,
        defaults={"encrypted_secret": encrypt_secret(secret), "confirmed_at": None, "last_timestep": -1, "created_at": timezone.now()},
    )
    uri = f"otpauth://totp/{quote('YEM:' + request.user.get_username())}?secret={secret}&issuer=YEM&algorithm=SHA1&digits=6&period=30"
    audit(request, "mfa_enrollment_started", request.user)
    return JsonResponse({"otpauth_uri": uri, "manual_secret": secret, "qr_image": make_qr_data_uri(uri)})


@require_POST
@authorized
def mfa_confirm(request):
    data, error = payload(request)
    if error is not None:
        return error
    if MFADevice.objects.filter(user=request.user, confirmed_at__isnull=False).exists():
        return JsonResponse({"error": "Double authentification déjà activée."}, status=409)
    if not verify_factor(request.user, data.get("code"), require_confirmed=False):
        return JsonResponse({"error": "Code invalide ou expiré."}, status=400)
    with transaction.atomic():
        device = MFADevice.objects.select_for_update().get(user=request.user)
        device.confirmed_at = timezone.now()
        device.save(update_fields=["confirmed_at"])
        codes = new_recovery_codes(device)
    request.session["mfa_verified"] = True
    audit(request, "mfa_enabled", request.user)
    return JsonResponse({"enabled": True, "recovery_codes": codes})


@require_POST
@authorized
def mfa_disable(request):
    data, error = payload(request)
    if error is not None:
        return error
    password = data.get("password")
    if not isinstance(password, str) or not request.user.check_password(password):
        return JsonResponse({"error": "Mot de passe incorrect."}, status=403)
    if not verify_factor(request.user, data.get("code")):
        return JsonResponse({"error": "Code de vérification invalide."}, status=403)
    MFADevice.objects.filter(user=request.user).delete()
    request.session["mfa_verified"] = False
    audit(request, "mfa_disabled", request.user)
    return JsonResponse({"enabled": False})


@require_GET
@authorized
def platform_audit(request):
    if not request.user.is_superuser or not request.session.get("mfa_verified", False):
        return JsonResponse({"error": "Accès plateforme réservé au super-administrateur avec MFA vérifié."}, status=403)
    rows = AuthAudit.objects.select_related("actor")[:100]
    return JsonResponse({"events": [
        {"id": str(e.pk), "event": e.event, "actor_id": str(e.actor_id) if e.actor_id else None,
         "created_at": e.created_at.isoformat(), "ip_hash": e.ip_hash[:12]}
        for e in rows
    ]})
