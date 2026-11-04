"""Super-administrator-assisted account recovery for school members.

This endpoint issues a short-lived Django password-reset URL, never the
password itself. The holder must set their own password. An existing TOTP/MFA
factor is not removed or bypassed.
"""
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.http import JsonResponse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from institutions.models import PlatformAudit, SchoolMember

from .security import audit, failure, is_locked, throttle_key
from .views import authorized, payload


@require_POST
@authorized
def admin_password_reset(request):
    if not request.user.is_superuser or not request.session.get("mfa_verified", False):
        return JsonResponse({"error": "Accès super-administrateur avec MFA requis."}, status=403)

    data, error = payload(request)
    if error is not None:
        return error
    if set(data) != {"school_id", "member_id", "reason", "current_password"}:
        return JsonResponse({"error": "Informations de réinitialisation incomplètes."}, status=422)

    school_id, member_id = data.get("school_id"), data.get("member_id")
    reason, password = data.get("reason"), data.get("current_password")
    if (not isinstance(school_id, str) or len(school_id) > 64
            or not isinstance(member_id, str) or len(member_id) > 64
            or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 240
            or not isinstance(password, str) or not 1 <= len(password) <= 1024):
        return JsonResponse({"error": "Identifiants ou motif invalides."}, status=422)

    # Reauthentication protects this exceptional privileged action from a
    # stolen but otherwise valid browser session. Brute force is throttled.
    key = throttle_key(request, "admin-password-reset", request.user.get_username())
    if is_locked(key):
        return JsonResponse({"error": "Réinitialisation temporairement bloquée."}, status=429)
    if not request.user.check_password(password):
        failure(key, limit=4)
        audit(request, "admin_reset_reauth_failed", request.user)
        return JsonResponse({"error": "Confirmation du super-administrateur incorrecte."}, status=403)

    try:
        from uuid import UUID
        school_uuid, member_uuid = UUID(school_id), UUID(member_id)
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "Compte ou établissement introuvable."}, status=404)

    member = (SchoolMember.objects.select_related("user", "school")
              .filter(pk=member_uuid, school_id=school_uuid).first())
    if member is None:
        return JsonResponse({"error": "Compte introuvable dans cet établissement."}, status=404)

    target = member.user
    if target.pk == request.user.pk or target.is_superuser or target.is_staff:
        return JsonResponse({"error": "Un compte de plateforme ne peut pas être réinitialisé ici."}, status=403)
    if not target.is_active or not member.active:
        return JsonResponse({"error": "Réactivez d'abord l'accès du compte si cela est autorisé."}, status=409)

    # Render deployments may not have SMTP enabled: an operator may deliver
    # the link only through an independently verified secure channel.
    base = settings.AUTH_PUBLIC_BASE_URL.strip().rstrip("/")
    if not base:
        base = request.build_absolute_uri("/").rstrip("/")
    if not base.startswith(("https://", "http://localhost:", "http://127.0.0.1:")):
        return JsonResponse({"error": "L'adresse publique YEM n'est pas configurée."}, status=503)

    uid = urlsafe_base64_encode(force_bytes(target.pk))
    token = default_token_generator.make_token(target)
    url = f"{base}/#/reset?uid={quote(uid)}&token={quote(token)}"

    # Audit without password, token, or URL: only actor, target, school and motive.
    PlatformAudit.objects.create(
        actor=request.user, school=member.school, event="password_reset_link_issued",
        subject=f"{target.get_username()} · {member.school.name}"[:180],
        reason=reason.strip(),
    )
    audit(request, "admin_reset_link_issued", request.user)
    response = JsonResponse({
        "issued": True,
        "username": target.get_username(),
        "school": member.school.name,
        "reset_url": url,
        "expires_in_minutes": settings.PASSWORD_RESET_TIMEOUT // 60,
        "instructions": "Vérifiez l'identité de la personne et transmettez ce lien par un canal privé sûr.",
    })
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    return response
