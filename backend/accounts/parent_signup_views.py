"""Public parent account signup with email verification.

No self-registered account receives membership, privileges or access to a
student. Every school guardian link still requires human verification.
"""
import re
from email.utils import parseaddr
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST, require_GET

from .security import audit, failure, is_locked, throttle_key
from .models import AuthAudit
from .views import payload

User = get_user_model()
USERNAME = re.compile(r"[A-Za-z0-9_.@+-]{3,50}\Z")
GENERIC = "Si votre inscription est recevable, un courriel de confirmation sera envoyé."


def registration_ready():
    return bool(settings.PASSWORD_RESET_ENABLED and settings.AUTH_PUBLIC_BASE_URL.startswith("https://")) or (
        bool(settings.PASSWORD_RESET_ENABLED and settings.ENVIRONMENT in ("development", "test"))
    )


def registration_test_mode():
    sender = parseaddr(settings.DEFAULT_FROM_EMAIL)[1].casefold()
    return settings.EMAIL_BACKEND == "accounts.email_backends.ResendEmailBackend" and sender.endswith("@resend.dev")


@require_GET
def registration_status(request):
    ready = registration_ready()
    return JsonResponse({"email_registration_available": ready,
                         "email_test_mode": ready and registration_test_mode(),
                         "confirmation_valid_minutes": settings.PASSWORD_RESET_TIMEOUT // 60})


def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = settings.AUTH_PUBLIC_BASE_URL.rstrip("/") + "/#/verify?uid=" + uid + "&token=" + token
    send_mail("YEM : vérifier votre compte parent",
              "Confirmez votre adresse email pour accéder à YEM Parents :\n" + url +
              "\n\nCe lien expire au bout de 30 minutes. Si vous n’avez pas demandé ce compte, ignorez ce message.",
              settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)



@require_POST
def register(request):
    if not registration_ready():
        return JsonResponse({"error": "Inscription indisponible : messagerie non configurée."}, status=503)
    data, error = payload(request)
    if error is not None:
        return error
    if set(data) != {"username", "first_name", "last_name", "email", "password"}:
        return JsonResponse({"error": "Informations de compte incomplètes."}, status=422)
    username = data.get("username")
    email = data.get("email")
    first = data.get("first_name")
    last = data.get("last_name")
    password = data.get("password")
    if not (isinstance(username,str) and USERNAME.fullmatch(username)
            and isinstance(first,str) and 1 <= len(first.strip()) <= 120
            and isinstance(last,str) and 1 <= len(last.strip()) <= 120
            and isinstance(email,str) and len(email) <= 254 and isinstance(password,str)):
        return JsonResponse({"error":"Données de compte invalides."},status=422)
    email=email.strip().lower()
    try:
        validate_email(email)
        validate_password(password, user=User(username=username, first_name=first, last_name=last, email=email))
    except ValidationError as exc:
        return JsonResponse({"error":" ".join(exc.messages)},status=422)
    key = throttle_key(request, "parent-registration", "all")
    if is_locked(key):
        return JsonResponse({"error":"Trop de tentatives. Réessayez plus tard."},status=429)
    failure(key, limit=5)
    if User.objects.filter(username__iexact=username).exists() or User.objects.filter(email__iexact=email).exists():
        audit(request,"parent_registration_duplicate")
        return JsonResponse({"message": GENERIC})
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username, first_name=first.strip(), last_name=last.strip(),
                email=email, password=password, is_active=False, is_staff=False, is_superuser=False,
            )
            send_verification_email(user)
    except IntegrityError:
        return JsonResponse({"message": GENERIC})
    except Exception:
        audit(request,"parent_registration_mail_error")
        message = "La création du compte a été interrompue pendant l’envoi du lien d’activation."
        if registration_test_mode():
            message += " En mode test, le lien est réservé à l’adresse associée au service d’envoi."
        return JsonResponse({"error": message}, status=503)
    audit(request,"parent_registration_requested",user)
    return JsonResponse({"message":GENERIC},status=201)


@require_POST
def verify(request):
    data, error = payload(request)
    if error is not None:
        return error
    if set(data) != {"uid","token"} or not all(isinstance(x,str) for x in data.values()):
        return JsonResponse({"error":"Lien de validation invalide."},status=422)
    try:
        uid=UUID(force_str(urlsafe_base64_decode(data["uid"])))
    except (ValueError,TypeError,OverflowError,UnicodeDecodeError):
        return JsonResponse({"error":"Lien de validation invalide."},status=422)
    with transaction.atomic():
        user=User.objects.select_for_update().filter(pk=uid,is_active=False).first()
        if user is None or not default_token_generator.check_token(user,data["token"]):
            return JsonResponse({"error":"Lien expiré, invalide ou déjà utilisé."},status=422)
        user.is_active=True
        user.save(update_fields=["is_active"])
    audit(request,"parent_registration_verified",user)
    return JsonResponse({"verified":True})


@require_POST
def resend_verification(request):
    """Reissue an expired mail only for identities created through parent signup."""
    if not registration_ready():
        return JsonResponse({"error":"Messagerie de confirmation indisponible."}, status=503)
    data, error = payload(request)
    if error is not None:
        return error
    email = data.get("email")
    if set(data) != {"email"} or not isinstance(email, str) or len(email) > 254:
        return JsonResponse({"error":"Adresse e-mail invalide."}, status=422)
    email = email.strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error":"Adresse e-mail invalide."}, status=422)
    key = throttle_key(request, "parent-resend", email)
    generic = JsonResponse({"message": GENERIC})
    if is_locked(key):
        return generic
    failure(key, limit=3)
    user = User.objects.filter(email__iexact=email, is_active=False).order_by("pk").first()
    if user is None or not AuthAudit.objects.filter(actor=user, event="parent_registration_requested").exists():
        return generic
    try:
        send_verification_email(user)
    except Exception:
        audit(request, "parent_registration_resend_failed", user)
        return generic  # Do not expose account existence via SMTP failures.
    audit(request, "parent_registration_resent", user)
    return generic
