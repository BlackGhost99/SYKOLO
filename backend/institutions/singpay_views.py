"""Parent payments to a single school's own merchant destination."""
import uuid
import json
from decimal import Decimal

from django.conf import settings
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.views import authorized
from .finance_models import FeeCharge
from .admission_finance import current_scholarship
from .finance_views import cleared_total
from .models import School, SchoolAudit
from .parent_admission_models import ParentAdmissionRequest
from .parent_payment_models import ParentPaymentAttempt
from .parent_payment_service import encrypt_secret, ProviderError
from .parent_views import guardian_links
from .services import owns_organization, has_permission
from .singpay_models import SingPayMerchant, SingPayIntent, SingPayEvent, SingPaySettlement
from .singpay_service import (IDENTIFIER, OPEN_STATES, digest, fee_quote, merchant_ready,
                              normalize_phone, initiate, reconcile)
from .views import access, parse_body, refuse, log_event


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def merchant_view(row):
    return {"configured": bool(row), "active": merchant_ready(row),
            "revision": row.revision if row else 0, "mode": row.mode if row else "test",
            "beneficiary": row.beneficiary_name if row else "",
            "enabled": row.enabled if row else False,
            "fee_basis_points": row.fee_basis_points if row else 0,
            "fee_fixed_xaf": row.fee_fixed_xaf if row else 0,
            "notice": "Activation suspendue jusqu'à validation du contrat de confirmation SingPay."}


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def merchant_config(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    # Receiving, approving or pricing rights cannot redirect school funds.
    if not owns_organization(request.user, school.organization):
        return refuse()
    if request.method == "GET":
        return JsonResponse(merchant_view(SingPayMerchant.objects.filter(school=school).first()))
    data, error = parse_body(request)
    if error is not None:
        return error
    required = {"revision", "wallet_id", "disbursement_id", "client_id", "client_secret",
                "beneficiary_name", "contract_reference", "mode", "enabled", "fee_basis_points", "fee_fixed_xaf"}
    if set(data) != required:
        return fail("Configuration marchande complète requise.")
    if (type(data["revision"]) is not int or type(data["enabled"]) is not bool
            or data["mode"] not in ("test", "live")
            or type(data["fee_basis_points"]) is not int or not 0 <= data["fee_basis_points"] <= 10000
            or type(data["fee_fixed_xaf"]) is not int or not 0 <= data["fee_fixed_xaf"] <= 100000):
        return fail("Configuration ou frais invalides.")
    for key in ("wallet_id", "disbursement_id", "client_id"):
        if not isinstance(data[key], str) or not IDENTIFIER.fullmatch(data[key]):
            return fail("Identifiant marchand invalide.")
    for key, limit in (("client_secret", 500), ("beneficiary_name", 180), ("contract_reference", 180)):
        if not isinstance(data[key], str) or not 1 <= len(data[key].strip()) <= limit:
            return fail("Secret, bénéficiaire et justificatif de contrat requis.")
    if not settings.AUTH_PUBLIC_BASE_URL.startswith("https://") or len(settings.YEM_PAYMENT_ENCRYPTION_KEY) < 32:
        return fail("HTTPS public et chiffrement serveur requis.", 503)
    if data["enabled"]:
        # Do not turn an unverified callback scheme into an operational payment gateway.
        return fail("Activation bloquée : recette et authentification callback à confirmer avec SingPay.", 409)
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            row = SingPayMerchant.objects.select_for_update().filter(school=school).first()
            if (row.revision if row else 0) != data["revision"]:
                return fail("Configuration modifiée, actualisez.", 409)
            if SingPayIntent.objects.filter(school=school, state__in=OPEN_STATES).exists():
                return fail("Rapprochez les paiements ouverts avant toute modification.", 409)
            if row is None:
                row = SingPayMerchant(school=school)
            else:
                row.revision += 1
            for key in ("wallet_id", "disbursement_id", "beneficiary_name", "contract_reference", "mode", "fee_basis_points", "fee_fixed_xaf"):
                setattr(row, key, data[key])
            row.encrypted_credentials = encrypt_secret(json.dumps({
                "client_id": data["client_id"], "client_secret": data["client_secret"],
            }))
            row.enabled = False
            row.save()
            log_event(school, request, "singpay_merchant_configured", school.pk)
    except IntegrityError:
        return fail("Ce portefeuille est déjà affecté à un autre établissement.", 409)
    except ProviderError:
        return fail("Chiffrement indisponible.", 503)
    return JsonResponse(merchant_view(row))


def owned_obligation(user, kind, object_id, lock=False):
    if kind == "charge":
        rows = FeeCharge.objects.select_for_update() if lock else FeeCharge.objects.all()
        row = rows.select_related("enrollment__student").filter(pk=object_id).first()
        if row and row.enrollment.active and guardian_links(user).filter(
                school_id=row.school_id, guardian__student_id=row.enrollment.student_id).exists():
            return row
    elif kind == "admission":
        rows = ParentAdmissionRequest.objects.select_for_update() if lock else ParentAdmissionRequest.objects.all()
        return rows.select_related("application__school").filter(pk=object_id, owner=user,
            application__school__is_active=True).first()
    return None


def obligation_school(row, kind):
    return row.school_id if kind == "charge" else row.application.school_id


def intent_view(row):
    return {"id": str(row.pk), "reference": row.reference, "state": row.state,
            "beneficiary": row.beneficiary_name, "school": str(row.school_id),
            "amount_xaf": row.amount_xaf, "total_parent_xaf": row.amount_xaf,
            "fee_xaf": row.fee_xaf, "estimated_school_net_xaf": row.amount_xaf-row.fee_xaf,
            "fee_payer": "school", "currency": "XAF", "mode": row.mode,
            "paid_confirmed": row.state == "success" and row.mode == "live",
            "receipt": str(row.payment_id) if row.payment_id else None,
            "notice": "Test prestataire : aucune dette réelle créditée." if row.mode == "test" else "Confirmation serveur obligatoire."}


@never_cache
@require_GET
@authorized
def quote(request, kind, object_id):
    row = owned_obligation(request.user, kind, object_id)
    if row is None:
        return fail("Frais introuvable.", 404)
    school_id = obligation_school(row, kind)
    merchant = SingPayMerchant.objects.filter(school_id=school_id).first()
    intents = SingPayIntent.objects.filter(**{kind: row}, payer=request.user).order_by("-created_at")[:20]
    balance = row.amount-cleared_total(row) if kind == "charge" else row.fee_amount_xaf
    return JsonResponse({"merchant": merchant_view(merchant), "balance_xaf": str(balance),
                         "payments": [intent_view(i) for i in intents]})


@never_cache
@require_POST
@authorized
def pay(request, kind, object_id):
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"amount_xaf", "channel", "phone", "idempotency_key", "merchant_revision"}:
        return fail("Montant, opérateur, téléphone, révision et clé d'opération requis.")
    try:
        key = uuid.UUID(data["idempotency_key"])
        phone = normalize_phone(data["phone"], data["channel"])
    except (ValueError, TypeError, AttributeError):
        return fail("Téléphone ou clé d'opération invalide.")
    if type(data["amount_xaf"]) is not int or not 100 <= data["amount_xaf"] <= 10000000 or type(data["merchant_revision"]) is not int:
        return fail("Montant entier XAF ou révision invalide.")
    request_hash = digest({**data, "phone": phone, "kind": kind, "object": str(object_id)})
    try:
        with transaction.atomic():
            # Lock school first, shared with configuration and finance batching.
            candidate = owned_obligation(request.user, kind, object_id)
            if candidate is None:
                return fail("Frais introuvable.", 404)
            school = School.objects.select_for_update().get(pk=obligation_school(candidate, kind))
            row = owned_obligation(request.user, kind, object_id, lock=True)
            if row is None:
                return fail("Accès familial révoqué.", 404)
            previous = SingPayIntent.objects.filter(payer=request.user, idempotency_key=key).first()
            if previous:
                return (JsonResponse(intent_view(previous)) if previous.request_hash == request_hash
                        else fail("Clé déjà utilisée avec une demande différente.", 409))
            # Check financial eligibility before merchant readiness: a verified
            # government award forbids another charge regardless of PSP state.
            if kind == "admission" and current_scholarship(row.application):
                return fail("Bourse gouvernementale déjà validée : paiement SingPay interdit.", 409)
            if SingPayIntent.objects.filter(**{kind: row}, state__in=OPEN_STATES).exists():
                return fail("Un paiement est ouvert : vérifiez-le avant un nouvel essai.", 409)
            merchant = SingPayMerchant.objects.filter(school=school).first()
            if not merchant_ready(merchant):
                return fail("SingPay n'est pas encore activé pour cet établissement.", 503)
            if merchant.revision != data["merchant_revision"]:
                return fail("Les conditions marchandes ont changé, actualisez.", 409)
            if kind == "charge":
                if row.currency != "XAF" or Decimal(data["amount_xaf"]) > row.amount-cleared_total(row):
                    return fail("Montant supérieur au solde XAF.", 409)
            else:
                if (row.payment_choice != "online" or data["amount_xaf"] != row.fee_amount_xaf
                        or row.application.status in ("rejected", "enrolled")):
                    return fail("Frais de dossier non payable.", 409)
                if ParentPaymentAttempt.objects.filter(request=row).exclude(state__in=("failed", "cancelled")).exists() or SingPayIntent.objects.filter(admission=row, state__in=("success", "test_success")).exists():
                    return fail("Paiement PayCentral ou SingPay existant : rapprochez le dossier.", 409)
            quoted = fee_quote(merchant, data["amount_xaf"])
            intent = SingPayIntent.objects.create(
                school=school, payer=request.user, **{kind: row}, idempotency_key=key,
                request_hash=request_hash, reference="YEMSP-"+uuid.uuid4().hex,
                wallet_id=merchant.wallet_id, disbursement_id=merchant.disbursement_id,
                merchant_revision=merchant.revision, mode=merchant.mode,
                beneficiary_name=merchant.beneficiary_name, amount_xaf=data["amount_xaf"],
                fee_xaf=quoted["fee_xaf"], phone=phone, channel=data["channel"],
            )
            SingPayEvent.objects.create(intent=intent, kind="created")
            log_event(school, request, "singpay_intent_created", intent.pk)
    except ProviderError as exc:
        return fail(str(exc), 409)
    except IntegrityError:
        return fail("Opération concurrente : actualisez sans relancer le débit.", 409)
    return JsonResponse(intent_view(initiate(intent, merchant)), status=201)


def parent_intent(user, intent_id):
    row = SingPayIntent.objects.filter(pk=intent_id, payer=user).first()
    if row and owned_obligation(user, "charge" if row.charge_id else "admission", row.charge_id or row.admission_id):
        return row
    return None


@never_cache
@require_POST
@authorized
def refresh(request, intent_id):
    row = parent_intent(request.user, intent_id)
    if row is None:
        return fail("Paiement introuvable.", 404)
    if row.state in ("success", "failed", "test_success"):
        return JsonResponse(intent_view(row))
    merchant = SingPayMerchant.objects.filter(school_id=row.school_id).first()
    try:
        if merchant is None:
            raise ProviderError("Compte marchand indisponible.")
        row = reconcile(row, merchant)
    except (ProviderError, IntegrityError):
        return fail("Vérification indisponible. Aucun nouvel essai de débit.", 503)
    return JsonResponse(intent_view(row))


@never_cache
@require_GET
@authorized
def receipt(request, intent_id):
    row = parent_intent(request.user, intent_id)
    if row is None:
        return fail("Paiement introuvable.", 404)
    if row.state != "success" or row.mode != "live":
        return fail("Aucun reçu de paiement réel confirmé.", 409)
    return JsonResponse({**intent_view(row), "confirmed_at": row.confirmed_at.isoformat(),
        "transaction_id": row.transaction_id, "scope": "Scolarité" if row.charge_id else "Frais de dossier uniquement",
        "notice": "Reçu de paiement vérifié ; le règlement effectif au marchand est à rapprocher séparément."})


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def staff_reconciliation(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.finance.approve"):
        return refuse()
    if request.method == "GET":
        rows = SingPayIntent.objects.filter(school=school).select_related("singpaysettlement").order_by("-created_at")[:250]
        payments = []
        for row in rows:
            item = intent_view(row)
            settled = getattr(row, "singpaysettlement", None)
            item["settlement"] = ({"statement_reference": settled.statement_reference,
                "received_net_xaf": settled.received_net_xaf, "observed_fee_xaf": settled.observed_fee_xaf,
                "approved": bool(settled.approved_at)} if settled else None)
            payments.append(item)
        return JsonResponse({"payments": payments,
                             "notice": "Succès du paiement distinct du règlement marchand ; relevé SingPay requis."})
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"intent"}:
        return fail("Identifiant de paiement requis.")
    try:
        row = SingPayIntent.objects.filter(school=school, pk=uuid.UUID(data["intent"])).first()
    except (ValueError, TypeError, AttributeError):
        row = None
    if row is None:
        return fail("Paiement introuvable.", 404)
    merchant = SingPayMerchant.objects.filter(school=school).first()
    if merchant is None:
        return fail("Compte marchand indisponible.", 503)
    try:
        row = reconcile(row, merchant)
    except (ProviderError, IntegrityError):
        return fail("Vérification indisponible, investigation nécessaire.", 503)
    SchoolAudit.objects.create(school=school, actor=request.user, event="singpay_reconciled", subject=str(row.pk))
    return JsonResponse(intent_view(row))


@never_cache
@require_POST
@authorized
def settlement(request, school_id, intent_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.finance.approve"):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    with transaction.atomic():
        intent = SingPayIntent.objects.select_for_update().filter(school=school, pk=intent_id).first()
        if intent is None:
            return fail("Paiement introuvable.", 404)
        if intent.state != "success" or intent.mode != "live":
            return fail("Paiement réel confirmé requis.", 409)
        existing = SingPaySettlement.objects.filter(intent=intent).first()
        if data == {"approve": True}:
            if existing is None:
                return fail("Relevé de règlement requis.", 409)
            if existing.submitted_by_id == request.user.pk:
                return fail("Un autre contrôleur doit approuver le rapprochement.", 403)
            if existing.approved_at is None:
                existing.approved_by = request.user
                existing.approved_at = timezone.now()
                existing.save(update_fields=["approved_by", "approved_at"])
                log_event(school, request, "singpay_settlement_approved", intent.pk)
        else:
            if set(data) != {"statement_reference", "received_net_xaf", "observed_fee_xaf"}:
                return fail("Référence de relevé, net reçu et frais constatés requis.")
            if (not isinstance(data["statement_reference"], str) or not 5 <= len(data["statement_reference"].strip()) <= 180
                    or any(type(data[k]) is not int or data[k] < 0 for k in ("received_net_xaf", "observed_fee_xaf"))
                    or data["received_net_xaf"]+data["observed_fee_xaf"] != intent.amount_xaf):
                return fail("Le net et les frais constatés doivent justifier exactement le brut.")
            if existing:
                return fail("Rapprochement déjà enregistré ; conserver la preuve et signaler toute correction.", 409)
            existing = SingPaySettlement.objects.create(intent=intent, submitted_by=request.user, **data)
            log_event(school, request, "singpay_settlement_submitted", intent.pk)
        return JsonResponse({"reference": intent.reference, "approved": bool(existing.approved_at),
            "received_net_xaf": existing.received_net_xaf, "observed_fee_xaf": existing.observed_fee_xaf,
            "fee_variance_xaf": existing.observed_fee_xaf-intent.fee_xaf,
            "notice": "Rapprochement documentaire du compte école, aucun transfert déclenché."})


@never_cache
@require_POST
@csrf_exempt
def webhook(request):
    # Published v1 Swagger only defines callbackURL, no HMAC/bearer/mTLS contract.
    # Do not invent a signature compatible with neither SingPay nor Gaboshop.
    # No body parsing, state change, credit, or provider request on this public route.
    return fail("Authentification callback SingPay non validée ; utiliser le rapprochement serveur.", 503)
