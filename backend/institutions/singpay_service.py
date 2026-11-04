"""SingPay v1, audited against the published Swagger, not SimPay.

No retries of a debit. All confirmations use authenticated GET by reference.
The public Swagger defines no callback authentication: webhook stays closed.
"""
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .finance_models import FeeCharge, FeePayment
from .parent_payment_models import ParentPaymentAttempt
from .parent_payment_service import decrypt_secret, ProviderError
from .singpay_models import SingPayIntent, SingPayEvent

BASE = "https://gateway.singpay.ga/v1"
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,120}\Z")
OPEN_STATES = ("initiating", "pending", "unknown", "review", "refund_review")


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fee_quote(merchant, amount):
    fee = int((Decimal(amount) * merchant.fee_basis_points / 10000).quantize(Decimal(1), rounding=ROUND_CEILING)) + merchant.fee_fixed_xaf
    if fee > amount:
        raise ProviderError("Frais contractuels supérieurs au montant.")
    return {"amount_xaf": amount, "fee_xaf": fee, "total_parent_xaf": amount,
            "estimated_school_net_xaf": amount-fee, "fee_payer": "school", "currency": "XAF"}


def merchant_ready(merchant):
    # Explicit global gate stays OFF pending provider callback contract and acceptance.
    return bool(merchant and merchant.enabled and merchant.encrypted_credentials
                and merchant.contract_reference and merchant.disbursement_id
                and len(settings.YEM_PAYMENT_ENCRYPTION_KEY) >= 32
                and getattr(settings, "YEM_SINGPAY_ENABLED", False)
                and (merchant.mode == "test" or settings.YEM_PAYMENTS_LIVE_ENABLED))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward merchant credentials to another host.


def provider_request(merchant, method, path, payload=None):
    if not merchant_ready(merchant):
        raise ProviderError("SingPay indisponible pour cet établissement.")
    credentials = json.loads(decrypt_secret(merchant.encrypted_credentials))
    raw = json.dumps(payload).encode() if payload is not None else None
    req = Request(BASE+path, data=raw, method=method, headers={
        "x-client-id": credentials["client_id"], "x-client-secret": credentials["client_secret"],
        "x-wallet": merchant.wallet_id, "Content-Type": "application/json", "Accept": "application/json",
    })
    try:
        with build_opener(NoRedirect()).open(req, timeout=15) as response:
            body = response.read(65537)
        if len(body) > 65536:
            raise ValueError()
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
        # Even a 4xx is not assumed proof of no debit. Never echo provider body.
        raise ProviderError("Réponse SingPay incertaine : rapprochement requis, aucun nouvel essai automatique.") from None


def normalize_phone(phone, channel):
    if not isinstance(phone, str) or channel not in ("airtel", "moov"):
        raise ValueError("Opérateur ou téléphone invalide.")
    phone = phone.strip().replace(" ", "")
    if re.fullmatch(r"\+241\d{8}", phone):
        phone = "0" + phone[4:]
    prefix = "07" if channel == "airtel" else "06"
    if not re.fullmatch(prefix + r"\d{7}", phone):
        raise ValueError("Numéro gabonais local à 9 chiffres incompatible avec l'opérateur.")
    return phone


def initiate(intent, merchant):
    payload = {"amount": intent.amount_xaf, "reference": intent.reference,
               "client_msisdn": intent.phone, "portefeuille": intent.wallet_id,
               "disbursement": intent.disbursement_id, "isTransfer": False}
    try:
        # Initiation response is deliberately never used to credit an obligation.
        response = provider_request(merchant, "POST", "/74/paiement" if intent.channel == "airtel" else "/62/paiement", payload)
        next_state, evidence = "pending", digest(response)
    except ProviderError:
        next_state, evidence = "unknown", ""
    with transaction.atomic():
        row = SingPayIntent.objects.select_for_update().get(pk=intent.pk)
        if row.state == "initiating":
            row.state = next_state
            row.save(update_fields=["state"])
            SingPayEvent.objects.create(intent=row, kind=next_state, evidence_hash=evidence)
    return row


def verified_transaction(intent, response):
    # GET by-reference officially returns transaction, not a guessed status alias.
    data = response
    wallet = data.get("portefeuille")
    if isinstance(wallet, dict):
        wallet = wallet.get("id") or wallet.get("_id")
    txid = data.get("id") or data.get("_id")
    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not (isinstance(txid, str) and IDENTIFIER.fullmatch(txid)
            and (not intent.transaction_id or intent.transaction_id == txid)
            and wallet == intent.wallet_id and data.get("reference") == intent.reference
            and data.get("client_msisdn") == intent.phone
            and amount.is_finite() and amount == intent.amount_xaf
            and data.get("isTransfer") is False):
        return None
    if data.get("status") == "Terminate" and data.get("result") == "Success":
        return "success", txid
    if data.get("status") == "Terminate" and data.get("result") in ("PasswordError", "BalanceError", "TimeOutError", "Error"):
        return "failed", txid
    if data.get("status") in ("Start", "Partenaire"):
        return "pending", txid
    return None  # Disbursement/Refund require investigation, never guess success.


def reconcile(intent, merchant):
    if (merchant.wallet_id != intent.wallet_id or merchant.disbursement_id != intent.disbursement_id
            or merchant.mode != intent.mode or merchant.revision != intent.merchant_revision):
        raise ProviderError("Configuration marchande modifiée : rapprochement spécialisé requis.")
    response = provider_request(merchant, "GET", "/transaction/api/search/by-reference/"+intent.reference)
    verified = verified_transaction(intent, response)
    with transaction.atomic():
        # Lock charge before intent, same order as parent initiation and manual ledger.
        charge = FeeCharge.objects.select_for_update().get(pk=intent.charge_id) if intent.charge_id else None
        if intent.admission_id:
            from .parent_admission_models import ParentAdmissionRequest
            ParentAdmissionRequest.objects.select_for_update().get(pk=intent.admission_id)
        row = SingPayIntent.objects.select_for_update().get(pk=intent.pk)
        row.checked_at = timezone.now()
        SingPayEvent.objects.create(intent=row, kind="verified" if verified else "mismatch", evidence_hash=digest(response))
        if row.payment_id or row.state in ("success", "test_success", "refund_review"):
            # Later refunds or inconsistent evidence cannot erase the receipt.
            # Preserve the original credit and require a compensating accounting review.
            if not verified or verified[0] != "success":
                row.state = "refund_review"
                row.save(update_fields=["state", "checked_at"])
                return row
            row.save(update_fields=["checked_at"])
            return row
        if row.state == "failed":
            row.save(update_fields=["checked_at"])
            return row
        if not verified:
            row.state = "review"
        else:
            state, txid = verified
            # Global unique provider transaction ID prevents cross-intent replay.
            if SingPayIntent.objects.exclude(pk=row.pk).filter(transaction_id=txid).exists():
                row.state = "review"
                row.save(update_fields=["state", "checked_at"])
                return row
            row.transaction_id = txid
            row.state = state
            if state == "success":
                row.confirmed_at = timezone.now()
                if row.mode != "live":
                    row.state = "test_success"  # Test wallets never reduce real debt.
                elif charge:
                    from .finance_views import cleared_total
                    if cleared_total(charge) + row.amount_xaf > charge.amount:
                        row.state = "review"  # Money received, allocation conflict: preserve evidence.
                    else:
                        row.payment = FeePayment.objects.create(
                            school_id=row.school_id, charge=charge, idempotency_key=row.pk,
                            amount=row.amount_xaf, currency="XAF", method="singpay",
                            reference=row.reference, paid_on=timezone.localdate(), recorded_by=None,
                        )
                else:
                    # Admission evidence stays separate from official enrollment/tuition.
                    if ParentPaymentAttempt.objects.filter(request_id=row.admission_id, state="success", provider_mode="live").exists():
                        row.state = "review"
        row.save()
        return row
