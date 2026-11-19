"""MFA platform merchant configuration and owner subscription payments."""
import json
import uuid
from django.conf import settings
from django.db import transaction, IntegrityError, connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .models import School
from .services import platform_only, owns_school, school_access
from .platform_admin_views import audit, denied
from .views import parse_body
from .singpay_views import fail, merchant_view
from .singpay_service import (merchant_ready, IDENTIFIER, verify_wallet_access, normalize_phone,
                             digest, fee_quote, ProviderError)
from .parent_payment_service import encrypt_secret
from .subscription_models import PlatformSubscription
from .subscription_views import representation
from .singpay_models import SingPayMerchant
from .commercial_singpay_models import PlatformSingPayMerchant as Merchant, SubscriptionSingPayIntent as Intent, SubscriptionSingPayEvent as Event
from .commercial_singpay import OPEN, initiate, reconcile

@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def merchant(request):
    if not platform_only(request):
        return denied()
    if request.method == "GET":
        return JsonResponse(merchant_view(Merchant.objects.first()))
    data, error = parse_body(request)
    if error is not None:
        return error
    required = {"revision", "wallet_id", "disbursement_id", "client_id", "client_secret", "beneficiary_name", "contract_reference", "mode", "enabled", "fee_basis_points", "fee_fixed_xaf"}
    if set(data) != required:
        return fail("Configuration marchande complète requise.")
    if (type(data["revision"]) is not int or type(data["enabled"]) is not bool or data["mode"] not in ("test", "live")
            or type(data["fee_basis_points"]) is not int or not 0 <= data["fee_basis_points"] <= 10000
            or type(data["fee_fixed_xaf"]) is not int or not 0 <= data["fee_fixed_xaf"] <= 100000):
        return fail("Configuration ou frais invalides.")
    if any(not isinstance(data[k], str) or not IDENTIFIER.fullmatch(data[k]) for k in ("wallet_id", "disbursement_id", "client_id")):
        return fail("Identifiant marchand invalide.")
    if any(not isinstance(data[k], str) or not 1 <= len(data[k].strip()) <= limit for k, limit in (("client_secret",500),("beneficiary_name",180),("contract_reference",180))):
        return fail("Secret, bénéficiaire et contrat requis.")
    if not settings.AUTH_PUBLIC_BASE_URL.startswith("https://") or len(settings.YEM_PAYMENT_ENCRYPTION_KEY) < 32:
        return fail("HTTPS et chiffrement serveur requis.", 503)
    try:
        candidate = Merchant(**{k:data[k] for k in ("wallet_id", "disbursement_id", "mode", "enabled", "beneficiary_name", "contract_reference", "fee_basis_points", "fee_fixed_xaf")}, encrypted_credentials=encrypt_secret(json.dumps({k:data[k] for k in ("client_id", "client_secret")})))
        if candidate.enabled:
            approved = getattr(settings,"YEM_SINGPAY_APPROVED_DESTINATIONS","").split(",")
            if not merchant_ready(candidate) or f"platform:{candidate.wallet_id}:{candidate.disbursement_id}:{candidate.mode}" not in approved:
                return fail("Destination BWETEK non autorisée par la plateforme.",409)
            verify_wallet_access(candidate)
        with transaction.atomic():
            # Serialize the singleton even when two different super-admins configure it.
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [736401229])
            current = Merchant.objects.select_for_update().first()
            if (current.revision if current else 0) != data["revision"]:
                return fail("Configuration modifiée, actualisez.",409)
            if Intent.objects.filter(state__in=OPEN).exists():
                return fail("Rapprochez les paiements ouverts avant modification.",409)
            if SingPayMerchant.objects.filter(wallet_id=candidate.wallet_id).exists():
                return fail("Un compte de scolarité ne peut recevoir les abonnements BWETEK.",409)
            candidate.revision = current.revision+1 if current else 1
            candidate.save(force_update=current is not None)
            audit(request,"platform_singpay_configured",candidate.pk)
    except ProviderError:
        return fail("Accès marchand ou chiffrement non confirmé.",409)
    except IntegrityError:
        return fail("Configuration modifiée, actualisez.",409)
    return JsonResponse(merchant_view(candidate))

def permitted(request, school):
    # Reuse the active school access boundary; only the legal owner can pay.
    return school_access(request.user,school.pk) and owns_school(request.user,school)

def intent_view(row):
    return {"id":str(row.pk), "state":row.state, "reference":row.reference,
            "amount_xaf":row.amount_xaf, "mode":row.mode,
            "receipt":f"/api/v1/schools/{row.subscription.year.school_id}/owner/subscriptions/{row.subscription_id}/payments/{row.payment_id}/receipt" if row.payment_id else None}

@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def payment(request, school_id, subscription_id):
    if not 1 <= subscription_id <= 2**63-1:
        return fail("Contrat introuvable.",404)
    school = School.objects.filter(pk=school_id).first()
    if not school or not permitted(request, school):
        return denied()
    sub = PlatformSubscription.objects.filter(pk=subscription_id,year__school=school).first()
    if not sub:
        return fail("Contrat introuvable.",404)
    merchant = Merchant.objects.first()
    if request.method == "GET":
        return JsonResponse({"merchant":merchant_view(merchant), "balance_xaf":representation(sub)["balance_xaf"],
            "payments":[intent_view(row) for row in sub.singpay_intents.order_by("-created_at")[:50]]})
    data,error = parse_body(request)
    if error is not None:
        return error
    try:
        if set(data) != {"amount_xaf","phone","channel","idempotency_key","merchant_revision"}:
            raise ValueError()
        amount = data["amount_xaf"]
        if type(amount) is not int or not 100 <= amount <= 10000000 or type(data["merchant_revision"]) is not int:
            raise ValueError()
        key = uuid.UUID(data["idempotency_key"])
        phone = normalize_phone(data["phone"],data["channel"])
    except (ValueError,TypeError,AttributeError):
        return fail("Montant, téléphone, opérateur ou clé invalide.")
    fingerprint = digest({"subscription":sub.pk,"amount":amount,"phone":phone,"channel":data["channel"],"revision":data["merchant_revision"]})
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            sub = PlatformSubscription.objects.select_for_update().get(pk=sub.pk)
            previous = Intent.objects.filter(payer=request.user,idempotency_key=key).first()
            if previous:
                if previous.request_hash != fingerprint:
                    return fail("Clé déjà utilisée pour une autre demande.",409)
                return JsonResponse(intent_view(previous))
            merchant = Merchant.objects.select_for_update().first()
            if not merchant_ready(merchant) or merchant.revision != data["merchant_revision"]:
                return fail("Compte BWETEK indisponible ou modifié.",409)
            if sub.singpay_intents.filter(state__in=OPEN).exists():
                return fail("Une opération est déjà ouverte : vérifiez son état.",409)
            if amount > representation(sub)["balance_xaf"]:
                return fail("Montant supérieur au solde du contrat.",409)
            quote = fee_quote(merchant,amount)
            row = Intent.objects.create(subscription=sub,payer=request.user,idempotency_key=key,request_hash=fingerprint,
                reference="YEMSUB"+uuid.uuid4().hex, wallet_id=merchant.wallet_id,disbursement_id=merchant.disbursement_id,
                merchant_revision=merchant.revision,mode=merchant.mode,beneficiary_name=merchant.beneficiary_name,
                amount_xaf=amount,fee_xaf=quote["fee_xaf"],phone=phone,channel=data["channel"])
            Event.objects.create(intent=row,kind="created")
    except IntegrityError:
        return fail("Demande concurrente : actualisez sans relancer un débit.",409)
    return JsonResponse(intent_view(initiate(row,merchant)),status=201)

@never_cache
@require_http_methods(["POST"])
@authorized
def refresh(request, school_id, subscription_id, intent_id):
    if not 1 <= subscription_id <= 2**63-1:
        return fail("Contrat introuvable.",404)
    school = School.objects.filter(pk=school_id).first()
    if not school or not permitted(request,school):
        return denied()
    row = Intent.objects.filter(pk=intent_id,subscription_id=subscription_id,subscription__year__school=school).first()
    if not row:
        return fail("Opération introuvable.",404)
    try:
        row = reconcile(row,Merchant.objects.first())
    except ProviderError:
        return fail("Vérification indisponible. Aucun nouveau débit n’a été déclenché.",503)
    return JsonResponse(intent_view(row))
