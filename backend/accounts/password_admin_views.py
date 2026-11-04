"""Audited assisted account recovery for YEM school and parent accounts.

Only an MFA-authenticated super-administrator, reauthenticated with their
own password, can issue a temporary reset URL. Existing MFA devices are
untouched. No plaintext account password or token is stored in audit logs.
"""
from urllib.parse import quote
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.http import JsonResponse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from institutions.models import PlatformAudit, SchoolMember

from .security import audit, clear_throttle, failure, is_locked, throttle_key
from .views import authorized, payload


def _check_admin(request, data, expected_fields):
    if not request.user.is_superuser or not request.session.get("mfa_verified", False):
        return None, JsonResponse({"error": "Accès super-administrateur avec MFA requis."}, status=403)

    if set(data) != expected_fields:
        return None, JsonResponse({"error": "Informations de réinitialisation incomplètes."}, status=422)

    reason, password = data.get("reason"), data.get("current_password")
    if (not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 240
            or not isinstance(password, str) or not 1 <= len(password) <= 1024):
        return None, JsonResponse({"error": "Motif ou confirmation invalides."}, status=422)

    key = throttle_key(request, "admin-password-reset", request.user.get_username())
    if is_locked(key):
        return None, JsonResponse({"error": "Réinitialisation temporairement bloquée."}, status=429)
    if not request.user.check_password(password):
        failure(key, limit=4)
        audit(request, "admin_reset_reauth_failed", request.user)
        return None, JsonResponse({"error": "Confirmation du super-administrateur incorrecte."}, status=403)
    clear_throttle(key)
    return reason.strip(), None


def _issue_link(request, target, reason, school=None):
    if target.pk == request.user.pk or target.is_superuser or target.is_staff:
        return JsonResponse({"error": "Un compte de plateforme ne peut pas être réinitialisé ici."}, status=403)
    if not target.is_active:
        return JsonResponse({"error": "Ce compte est désactivé ou en attente d'activation."}, status=409)

    base = settings.AUTH_PUBLIC_BASE_URL.strip().rstrip("/")
    if not base:
        base = request.build_absolute_uri("/").rstrip("/")
    if not base.startswith(("https://", "http://localhost:", "http://127.0.0.1:")):
        return JsonResponse({"error": "L'adresse publique YEM n'est pas configurée."}, status=503)

    uid = urlsafe_base64_encode(force_bytes(target.pk))
    token = default_token_generator.make_token(target)
    reset_url = f"{base}/#/reset?uid={quote(uid)}&token={quote(token)}"
    subject = f"{target.get_username()} · {school.name}" if school else f"Parent · {target.get_username()}"

    PlatformAudit.objects.create(
        actor=request.user, school=school, event="password_reset_link_issued",
        subject=subject[:180], reason=reason,
    )
    audit(request, "admin_reset_link_issued", request.user)
    response = JsonResponse({
        "issued": True,
        "username": target.get_username(),
        "reset_url": reset_url,
        "expires_in_minutes": settings.PASSWORD_RESET_TIMEOUT // 60,
        "instructions": "Vérifiez l'identité du titulaire et remettez ce lien par un canal privé.",
    })
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    return response


@require_POST
@authorized
def admin_password_reset(request):
    """School accounts: scope by the selected school and membership UUID."""
    data, error = payload(request)
    if error is not None:
        return error
    reason, error = _check_admin(request, data, {
        "school_id", "member_id", "reason", "current_password",
    })
    if error is not None:
        return error

    school_id, member_id = data.get("school_id"), data.get("member_id")
    if (not isinstance(school_id, str) or len(school_id) > 64
            or not isinstance(member_id, str) or len(member_id) > 64):
        return JsonResponse({"error": "Compte ou établissement introuvable."}, status=404)
    try:
        school_uuid, member_uuid = UUID(school_id), UUID(member_id)
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "Compte ou établissement introuvable."}, status=404)

    member = (SchoolMember.objects.select_related("user", "school")
              .filter(pk=member_uuid, school_id=school_uuid).first())
    if member is None:
        return JsonResponse({"error": "Compte introuvable dans cet établissement."}, status=404)
    if not member.active:
        return JsonResponse({"error": "Cet accès scolaire est suspendu."}, status=409)
    return _issue_link(request, member.user, reason, school=member.school)


@require_POST
@authorized
def admin_parent_password_reset(request):
    """Independent parent accounts: exact username + email, no school-data access."""
    data, error = payload(request)
    if error is not None:
        return error
    reason, error = _check_admin(request, data, {
        "username", "email", "reason", "current_password",
    })
    if error is not None:
        return error

    username, email = data.get("username"), data.get("email")
    if (not isinstance(username, str) or not 1 <= len(username.strip()) <= 150
            or not isinstance(email, str) or not 3 <= len(email.strip()) <= 254
            or "@" not in email):
        return JsonResponse({"error": "Identifiant et adresse e-mail invalides."}, status=422)

    user = get_user_model().objects.filter(
        username__iexact=username.strip(), email__iexact=email.strip(),
        is_active=True, is_superuser=False, is_staff=False,
    ).first()
    if user is None or SchoolMember.objects.filter(user=user).exists():
        return JsonResponse({"error": "Compte parent introuvable avec ces informations."}, status=404)
    return _issue_link(request, user, reason)
