"""Admission payment gateway, staff fee setup and parent-owned receipts/status.

Independent of tuition ledger, strict school isolation. Never mark success from
client claims or an unsigned callback. Settlement belongs to each school's own
merchant account; YEM never accepts a shared platform merchant key here.
"""
import json
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.views import authorized
from .academic_models import AcademicLevel, AcademicYear
from .admission_models import AdmissionEvent
from .admission_finance import current_scholarship
from .admission_scholarship_amounts import admission_due, grant_summary
from .parent_admission_models import ParentAdmissionRequest
from .parent_payment_models import ParentPaymentAttempt, SchoolAdmissionFee, SchoolPaymentGateway
from .parent_payment_service import (
    ProviderError, apply_verified_status, decrypt_secret, encrypt_secret,
    gateway_configured, paycentral_request, verified_money, verified_transaction,
    webhook_signature_ok, TRANSACTION_ID,
)
from .services import has_permission
from .views import access, log_event, parse_body, refuse


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def gateway_for(school):
    return SchoolPaymentGateway.objects.filter(school=school).first()


def safe_gateway_view(row):
    return {
        "revision": row.revision if row else 0,
        "mode": row.mode if row else "sandbox",
        "enabled": row.enabled if row else False,
        "has_keys": bool(row and row.encrypted_api_key and row.encrypted_webhook_secret),
        "live_enabled_by_platform": settings.YEM_PAYMENTS_LIVE_ENABLED,
        "encryption_ready": len(settings.YEM_PAYMENT_ENCRYPTION_KEY) >= 32,
        "active": gateway_configured(row),
        "provider": "paycentral",
        "webhook_url": settings.AUTH_PUBLIC_BASE_URL.rstrip("/") + "/api/v1/parents/paycentral/webhook",
    }


def fee_view(row):
    return {"id": str(row.pk), "year": str(row.year_id),
            "level": str(row.level_id), "amount_xaf": row.amount_xaf,
            "active": row.active, "revision": row.revision}


def staff_access(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not (has_permission(request.user, school, "school.admissions.manage")
            and has_permission(request.user, school, "school.finance.manage")):
        return None, refuse()
    return school, None


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def school_gateway(request, school_id):
    school, error = staff_access(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        return JsonResponse(safe_gateway_view(gateway_for(school)))
    data, error = parse_body(request)
    if error is not None:
        return error
    required = {"revision", "mode", "enabled", "api_key", "webhook_secret"}
    if set(data) != required or type(data["revision"]) is not int or data["revision"] < 0:
        return fail("Paramètres de paiement invalides.")
    if type(data["enabled"]) is not bool or data["mode"] not in ("sandbox", "live"):
        return fail("Environnement de paiement invalide.")
    if any(not isinstance(data[key], str) or len(data[key]) > 300 for key in ("api_key", "webhook_secret")):
        return fail("Clés API invalides.")
    if data["enabled"] and data["mode"] == "live" and not settings.YEM_PAYMENTS_LIVE_ENABLED:
        return fail("Le paiement réel doit être autorisé par l'exploitant YEM.", 409)
    if data["enabled"] and not settings.AUTH_PUBLIC_BASE_URL.startswith("https://"):
        return fail("URL publique HTTPS requise pour les confirmations du prestataire.", 409)
    if len(settings.YEM_PAYMENT_ENCRYPTION_KEY) < 32 and data["enabled"]:
        return fail("Clé de chiffrement serveur manquante.", 503)
    try:
        with transaction.atomic():
            from .models import School
            School.objects.select_for_update().get(pk=school.pk)
            row = SchoolPaymentGateway.objects.select_for_update().filter(school=school).first()
            if (row.revision if row else 0) != data["revision"]:
                return fail("La configuration a changé : actualisez la fiche.", 409)
            created = row is None
            if created:
                row = SchoolPaymentGateway(school=school)
            unsettled = ParentPaymentAttempt.objects.filter(
                school=school, state__in=("initiating", "pending", "unknown"),
            ).exists()
            if unsettled and (
                (data["api_key"] and row.encrypted_api_key)
                or (data["webhook_secret"] and row.encrypted_webhook_secret)
                or (row.mode != data["mode"])
            ):
                return fail("Des paiements sont en cours : rapprochez-les avant de changer les clés ou l'environnement.", 409)
            if data["api_key"]:
                expected = "sk_live_" if data["mode"] == "live" else "sk_sandbox_"
                if not data["api_key"].startswith(expected):
                    return fail("Clé incompatible avec l'environnement choisi.")
                row.encrypted_api_key = encrypt_secret(data["api_key"])
            elif row.mode != data["mode"] and row.encrypted_api_key:
                return fail("Une nouvelle clé API est requise pour changer d'environnement.")
            if row.mode != data["mode"] and row.encrypted_webhook_secret and not data["webhook_secret"]:
                return fail("Un nouveau secret webhook est requis au changement d'environnement.")
            if data["webhook_secret"]:
                if not data["webhook_secret"].startswith("whsec_"):
                    return fail("Le secret webhook doit venir du tableau de bord PayCentral.")
                row.encrypted_webhook_secret = encrypt_secret(data["webhook_secret"])
            row.mode = data["mode"]
            row.enabled = data["enabled"]
            if row.enabled and not row.encrypted_api_key:
                return fail("Clé API marchande obligatoire.")
            if row.enabled and not row.encrypted_webhook_secret:
                return fail("Secret webhook obligatoire.")
            if row.enabled and not gateway_configured(row):
                return fail("Configuration du prestataire incomplète.", 409)
            row.revision = 1 if created else row.revision + 1
            row.full_clean()
            row.save()
            log_event(school, request, "admission_gateway_updated", school.pk)
    except ProviderError as exc:
        return fail(str(exc), 503)
    return JsonResponse(safe_gateway_view(row))


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def school_admission_fees(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.finance.manage"):
        return refuse()
    if request.method == "GET":
        rows = SchoolAdmissionFee.objects.filter(school=school).order_by("year_id", "level_id")
        return JsonResponse({
            "fees": [fee_view(row) for row in rows],
            "years": list(AcademicYear.objects.filter(school=school, active=True)
                          .order_by("-start_date").values("id", "name")),
            "levels": list(AcademicLevel.objects.filter(school=school, active=True)
                           .order_by("name").values("id", "name")),
        })
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"year", "level", "revision", "amount_xaf", "active"}:
        return fail("Paramètres de frais incomplets.")
    if (type(data["revision"]) is not int or data["revision"] < 0
            or type(data["amount_xaf"]) is not int
            or not 100 <= data["amount_xaf"] <= 10000000
            or type(data["active"]) is not bool):
        return fail("Montant XAF ou révision invalide.")
    try:
        year = AcademicYear.objects.get(pk=data["year"], school=school, active=True)
        level = AcademicLevel.objects.get(pk=data["level"], school=school, active=True)
    except (ValueError, TypeError, AcademicYear.DoesNotExist, AcademicLevel.DoesNotExist):
        return fail("Année ou niveau inconnu.", 404)
    with transaction.atomic():
        from .models import School
        School.objects.select_for_update().get(pk=school.pk)
        row = SchoolAdmissionFee.objects.select_for_update().filter(
            school=school, year=year, level=level,
        ).first()
        if (row.revision if row else 0) != data["revision"]:
            return fail("Le barème a changé. Actualisez avant de modifier.", 409)
        created = row is None
        if created:
            row = SchoolAdmissionFee(school=school, year=year, level=level)
        row.amount_xaf = data["amount_xaf"]
        row.active = data["active"]
        row.revision = 1 if created else row.revision + 1
        row.full_clean()
        row.save()
        log_event(school, request, "admission_fee_updated", row.pk)
    return JsonResponse(fee_view(row))


def public_payment_availability(school, year, level):
    fee = SchoolAdmissionFee.objects.filter(school=school, year=year, level=level, active=True).first()
    gateway = gateway_for(school)
    return fee, bool(fee and gateway_configured(gateway)
                     and settings.AUTH_PUBLIC_BASE_URL.startswith("https://"))


def attempt_view(row):
    return {
        "id": str(row.pk), "request": str(row.request_id),
        "amount_xaf": row.amount_xaf, "currency": row.currency,
        "channel": row.channel, "state": row.state,
        "provider_mode": row.provider_mode,
        "merchant_reference": row.merchant_reference,
        "transaction_reference": row.provider_reference if row.state in ("success", "refunded") else "",
        "paid_confirmed": row.state == "success" and row.provider_mode == "live",
        "notice": ("Paiement SIMULÉ : aucune somme reçue." if row.provider_mode == "sandbox"
                   else "Seul le prestataire confirme un paiement, jamais l'écran parent."),
        "created_at": row.created_at.isoformat(),
    }


@never_cache
@require_GET
@authorized
def parent_payment_status(request, application_id):
    row = ParentAdmissionRequest.objects.filter(
        pk=application_id, owner=request.user,
    ).first()
    if row is None:
        return fail("Demande introuvable.", 404)
    attempts = ParentPaymentAttempt.objects.filter(
        request=row, payer=request.user,
    ).order_by("-created_at")
    return JsonResponse({"payments": [attempt_view(p) for p in attempts[:15]],
                         "amounts": grant_summary(row.application)})


@never_cache
@require_POST
@authorized
def parent_pay(request, application_id):
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"channel", "phone"}:
        return fail("Moyen de paiement et téléphone obligatoires.")
    channel, phone = data["channel"], data["phone"]
    if channel not in ("airtel", "moov") or not isinstance(phone, str):
        return fail("Opérateur ou numéro de téléphone invalide.")
    phone = phone.strip()
    if not re.fullmatch(r"\+241\d{8,9}", phone):
        return fail("Numéro gabonais au format international +241 requis.")
    with transaction.atomic():
        # Shared lock order with scholarships, SingPay and cash: school first,
        # then the family request. This prevents reversed-lock deadlocks when
        # two payment channels are initiated at the same time.
        school_id = ParentAdmissionRequest.objects.filter(
            pk=application_id, owner=request.user,
        ).values_list("application__school_id", flat=True).first()
        if school_id is None:
            return fail("Demande introuvable.", 404)
        from .models import School
        School.objects.select_for_update().get(pk=school_id)
        link = ParentAdmissionRequest.objects.select_for_update().select_related(
            "application__school", "child",
        ).filter(pk=application_id, owner=request.user,
                 application__school_id=school_id).first()
        if link is None:
            return fail("Demande introuvable.", 404)
        amount_due = admission_due(link.application)
        if amount_due == 0:
            return fail("Bourse gouvernementale : frais d'inscription intégralement pris en charge, aucun paiement requis.", 409)
        if amount_due < 100:
            return fail("Solde inférieur au minimum encaissable : l'école doit ajuster la bourse.", 409)
        from .singpay_models import SingPayIntent
        if SingPayIntent.objects.filter(admission=link).exclude(state="failed").exists():
            return fail("Paiement SingPay existant : rapprochez-le avant un paiement PayCentral.", 409)
        if link.payment_choice != "online" or not link.fee_amount_xaf:
            return fail("Cette candidature ne prévoit pas de paiement en ligne.", 409)
        if link.application.status in ("rejected", "enrolled"):
            return fail("La candidature n'est plus ouverte au paiement.", 409)
        existing = ParentPaymentAttempt.objects.filter(
            request=link,
        ).order_by("-created_at").first()
        if existing and existing.state not in ("failed", "cancelled"):
            return JsonResponse(attempt_view(existing), status=200)
        school = link.application.school
        gateway = gateway_for(school)
        if not gateway_configured(gateway) or not settings.AUTH_PUBLIC_BASE_URL.startswith("https://"):
            return fail("Paiement en ligne indisponible pour cet établissement.", 503)
        attempt = ParentPaymentAttempt(
            request=link, payer=request.user, school=school,
            amount_xaf=amount_due, channel=channel, payer_phone=phone,
            provider_mode=gateway.mode, merchant_reference="YEM-"+uuid.uuid4().hex,
        )
        attempt.full_clean()
        attempt.save()
    # Network I/O deliberately OUTSIDE the database lock.
    try:
        response = paycentral_request(gateway, "POST", "/payment/initiate", {
            "amount": attempt.amount_xaf, "currency": "XAF",
            "provider": channel, "phone": phone,
            "description": "Frais de dossier d'admission YEM",
            "merchant_reference": attempt.merchant_reference,
            "callback_url": settings.AUTH_PUBLIC_BASE_URL.rstrip("/") + "/api/v1/parents/paycentral/webhook",
        })
        # PayCentral documents the transaction fields inside 'data'.
        # Require exact amount/currency/provider, even on a successful HTTP status.
        payload_data = response.get("data") if isinstance(response.get("data"), dict) else response
        transaction_id = payload_data.get("transaction_id")
        if response.get("success") is not True:
            raise ProviderError("Le prestataire n'a pas confirmé l'initiation.")
        if not (isinstance(transaction_id, str) and TRANSACTION_ID.fullmatch(transaction_id)):
            raise ProviderError("Identifiant de transaction invalide.")
        if payload_data.get("provider") != channel or not verified_money(payload_data, attempt.amount_xaf):
            raise ProviderError("La réponse du prestataire ne correspond pas au dossier.")
        if payload_data.get("status") not in ("pending", "processing"):
            raise ProviderError("Statut d'initiation non reconnu.")
        with transaction.atomic():
            locked = ParentPaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
            if locked.transaction_id and locked.transaction_id != transaction_id:
                return fail("Transaction incompatible. Contactez l'école.", 409)
            locked.transaction_id = transaction_id
            if locked.state == "initiating":
                locked.state = "pending"
            locked.save(update_fields=["transaction_id", "state", "updated_at"])
            attempt = locked
    except ProviderError as exc:
        with transaction.atomic():
            locked = ParentPaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
            if locked.state == "initiating":
                locked.state = "failed" if exc.conclusive else "unknown"
                locked.save(update_fields=["state", "updated_at"])
        return fail(str(exc), 422 if exc.conclusive else 503)
    return JsonResponse(attempt_view(attempt), status=201)


@never_cache
@require_POST
@csrf_exempt
def paycentral_webhook(request):
    # Reject anything over 8 KiB before parsing. Never log raw payloads or secrets.
    if request.content_type != "application/json":
        return fail("JSON requis.", 415)
    if int(request.META.get("CONTENT_LENGTH") or 0) > 8192 or len(request.body) > 8192:
        return fail("Payload trop volumineux.", 413)
    try:
        body = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return fail("JSON invalide.")
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        return fail("Événement invalide.")
    data = body["data"]
    reference = data.get("merchant_reference")
    if not isinstance(reference, str) or not re.fullmatch(r"YEM-[0-9a-f]{32}", reference):
        return fail("Événement inconnu.", 401)
    with transaction.atomic():
        attempt = ParentPaymentAttempt.objects.select_for_update().select_related(
            "school",
        ).filter(merchant_reference=reference).first()
        if attempt is None:
            return fail("Événement inconnu.", 401)
        gateway = gateway_for(attempt.school)
        if gateway is None:
            return fail("Passerelle absente.", 401)
        try:
            if not webhook_signature_ok(gateway, request.body, request.META.get("HTTP_X_PAYCENTRAL_SIGNATURE", "")):
                return fail("Signature invalide.", 401)
        except ProviderError:
            return fail("Signature non vérifiable.", 503)
        raw_status = data.get("status")
        if body.get("event") not in {"payment.success", "payment.failed", "payment.cancelled", "payment.pending", "payment.updated", "payment.refunded"}:
            return fail("Événement non reconnu.", 422)
        if (not verified_transaction(attempt, data, signed_webhook=True) or raw_status not in (
            "pending", "processing", "success", "failed", "cancelled", "refunded"
        )):
            return fail("Transaction incohérente.", 409)
        if body["event"] != "payment.updated" and not body["event"].endswith(raw_status):
            if not (body["event"] == "payment.pending" and raw_status == "processing"):
                return fail("Statut et événement incohérents.", 409)
        # Never replace the canonical initiation/status-API transaction ID
        # with the webhook's possibly distinct signed event UUID. This also
        # handles a webhook that beats the initiation HTTP response.
        apply_verified_status(attempt, raw_status, data.get("provider_reference", ""))
    return JsonResponse({"received": True})


@never_cache
@require_POST
@authorized
def parent_payment_refresh(request, application_id):
    link = ParentAdmissionRequest.objects.filter(pk=application_id, owner=request.user).first()
    if link is None:
        return fail("Demande introuvable.", 404)
    with transaction.atomic():
        attempt = ParentPaymentAttempt.objects.select_for_update().filter(
            request=link, payer=request.user,
        ).order_by("-created_at").first()
        if attempt is None:
            return fail("Aucun paiement à vérifier.", 404)
        if attempt.state in ("success", "failed", "cancelled", "refunded"):
            return JsonResponse(attempt_view(attempt))
        if not attempt.transaction_id:
            return fail("Rapprochement en attente : contactez l'établissement.", 409)
        if attempt.last_checked_at and timezone.now()-attempt.last_checked_at < timedelta(seconds=30):
            return JsonResponse(attempt_view(attempt))
        attempt.last_checked_at = timezone.now()
        attempt.save(update_fields=["last_checked_at"])
    gateway = gateway_for(attempt.school)
    try:
        result = paycentral_request(gateway, "GET", "/payment/"+attempt.transaction_id+"/status")
    except ProviderError:
        return fail("Statut du prestataire temporairement indisponible.", 503)
    data = result.get("transaction", {})
    if not isinstance(data, dict) or not verified_transaction(attempt, data):
        return fail("Réponse de vérification incohérente.", 409)
    with transaction.atomic():
        locked = ParentPaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        apply_verified_status(locked, data.get("status"), data.get("provider_reference", ""))
        attempt = locked
    return JsonResponse(attempt_view(attempt))


@never_cache
@require_GET
@authorized
def staff_admission_payments(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not (has_permission(request.user, school, "school.finance.read")
            or has_permission(request.user, school, "school.admissions.read")):
        return refuse()
    rows = ParentPaymentAttempt.objects.select_related("request__application").filter(
        school=school,
    ).order_by("-created_at")[:200]
    return JsonResponse({"payments": [
        {**attempt_view(row), "application": str(row.request.application_id)}
        for row in rows
    ]})


@never_cache
@require_GET
@authorized
def family_notifications(request):
    """Private inbox of school decisions and admission payment outcomes."""
    events = AdmissionEvent.objects.select_related(
        "application__school",
    ).filter(application__parent_request__owner=request.user).order_by("-at")[:100]
    messages = [{
        "id": str(e.pk), "kind": "admission",
        "school": e.application.school.name,
        "status": e.new_status, "at": e.at.isoformat(),
        "message": {
            "submitted": "Demande d'admission reçue", "review": "Dossier en cours d'étude",
            "accepted": "Admission accordée", "rejected": "Décision d'admission communiquée",
            "enrolled": "Inscription officielle confirmée",
            "cash_received": "Paiement en espèces reçu à la caisse. Reçu disponible dans Mes demandes.",
            "cash_simulated": "Paiement de test validé au guichet. Aucune somme reçue ; document de simulation disponible.",
            "cash_cancelled": "Un reçu de paiement en espèces a été annulé par l’administration.",
            "award_approved": "Bourse de l’État validée par l’établissement. Prise en charge enregistrée sans paiement du parent.",
            "award_revoked": "La décision de bourse a été annulée par la direction avant inscription.",
        }.get(e.new_status, "Mise à jour d'admission"),
    } for e in events]
    payments = ParentPaymentAttempt.objects.select_related("school").filter(
        payer=request.user, state__in=("success", "failed", "cancelled", "refunded"),
    ).order_by("-updated_at")[:100]
    messages += [{
        "id": str(p.pk), "kind": "payment", "school": p.school.name,
        "status": p.state, "at": p.updated_at.isoformat(),
        "message": "Paiement en simulation" if p.provider_mode == "sandbox" else {
            "success": "Paiement confirmé par le prestataire",
            "failed": "Paiement refusé", "cancelled": "Paiement annulé",
            "refunded": "Paiement remboursé",
        }.get(p.state, "Paiement mis à jour"),
    } for p in payments]
    return JsonResponse({"notifications": sorted(messages, key=lambda x: x["at"], reverse=True)[:100]})
