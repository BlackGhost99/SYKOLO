"""PayCentral protocol for school-owned Mobile Money merchant accounts.

No API keys are exposed to browsers; no provider callback is trusted without
its HMAC signature AND an amount/currency/reference cross-check.
"""
import base64
import hashlib
import hmac
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils import timezone

PAYCENTRAL_API = "https://api-paycentral.gabondunumerique.com/api/v1"
TRANSACTION_ID = re.compile(r"[a-zA-Z0-9_-]{8,120}\Z")


class ProviderError(Exception):
    def __init__(self, message, *, conclusive=False):
        super().__init__(message)
        self.conclusive = conclusive


def key_cipher():
    key = settings.YEM_PAYMENT_ENCRYPTION_KEY
    if not key or len(key) < 32:
        raise ProviderError("Le chiffrement des clés de paiement n'est pas configuré.")
    digest = hashlib.sha256(("yem-school-gateway-v1:" + key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value):
    return key_cipher().encrypt(value.encode()).decode()


def decrypt_secret(value):
    try:
        return key_cipher().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ProviderError("La clé de paiement est inaccessible.") from exc


def gateway_configured(gateway):
    return bool(
        gateway and gateway.enabled and gateway.encrypted_api_key
        and gateway.encrypted_webhook_secret
        and settings.YEM_PAYMENT_ENCRYPTION_KEY and len(settings.YEM_PAYMENT_ENCRYPTION_KEY) >= 32
        and (gateway.mode == "sandbox" or settings.YEM_PAYMENTS_LIVE_ENABLED)
    )


def paycentral_request(gateway, method, endpoint, data=None):
    if not gateway_configured(gateway):
        raise ProviderError("Paiements en ligne indisponibles pour cet établissement.")
    api_key = decrypt_secret(gateway.encrypted_api_key)
    if gateway.mode == "live" and not api_key.startswith("sk_live_"):
        raise ProviderError("Clé marchande de production incompatible.")
    if gateway.mode == "sandbox" and not api_key.startswith("sk_sandbox_"):
        raise ProviderError("Clé de simulation incompatible.")
    encoded = json.dumps(data, separators=(",", ":")).encode() if data is not None else None
    request = Request(
        PAYCENTRAL_API + endpoint,
        data=encoded, method=method,
        headers={"X-Api-Key": api_key, "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read(32769)
            if len(body) > 32768:
                raise ProviderError("Réponse du prestataire trop volumineuse.")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError()
            return data
    except HTTPError as exc:
        # 409: duplicate merchant_reference; recover same transaction, never generate another charge.
        if exc.code == 409:
            try:
                body = json.loads(exc.read(8192))
                if isinstance(body, dict) and body.get("transaction_id"):
                    return body
            except (ValueError, UnicodeDecodeError):
                pass
            raise ProviderError("Paiement déjà initié, vérification nécessaire.")
        if exc.code in (400, 401, 402, 403, 404, 422):
            raise ProviderError("Prestataire : demande refusée ou compte marchand non autorisé.", conclusive=True)
        raise ProviderError("Prestataire temporairement indisponible.")
    except (URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
        raise ProviderError("Connexion au prestataire impossible, vérification nécessaire.")


def verified_money(data, amount):
    if data.get("currency") != "XAF":
        return False
    try:
        observed = Decimal(str(data.get("amount")))
        return observed.is_finite() and observed == Decimal(amount)
    except (InvalidOperation, ValueError, TypeError):
        return False


def verified_transaction(attempt, data, *, signed_webhook=False):
    transaction_id = data.get("transaction_id") or data.get("id")
    # PayCentral's published initiation example uses a ULID while its signed
    # webhook example uses a UUID in 'data.id'. A valid HMAC plus matching
    # merchant reference, operator, currency and amount permits that difference.
    # For status API responses, keep strict ID matching (no webhook HMAC).
    if attempt.transaction_id and transaction_id != attempt.transaction_id and not signed_webhook:
        return False
    return bool(
        isinstance(transaction_id, str) and TRANSACTION_ID.fullmatch(transaction_id)
        and data.get("merchant_reference") == attempt.merchant_reference
        and data.get("provider") == attempt.channel
        and verified_money(data, attempt.amount_xaf)
    )


def webhook_signature_ok(gateway, raw, signature):
    if not isinstance(signature, str) or len(signature) != 71:
        return False
    secret = decrypt_secret(gateway.encrypted_webhook_secret)
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def apply_verified_status(attempt, status, provider_reference=""):
    """Call only after trusted HMAC event or authenticated PayCentral status API."""
    if status in ("pending", "processing"):
        next_state = "pending"
    elif status in {"success", "failed", "cancelled", "refunded"}:
        next_state = status
    else:
        return False
    if attempt.state == "refunded":
        return False
    if attempt.state == "success" and next_state != "refunded":
        return False
    if attempt.state in ("failed", "cancelled") and next_state not in ("failed", "cancelled"):
        return False
    if attempt.state == next_state:
        return False
    attempt.state = next_state
    attempt.provider_reference = str(provider_reference or "")[:140]
    attempt.last_checked_at = timezone.now()
    if next_state in ("success", "failed", "cancelled", "refunded"):
        attempt.finalized_at = timezone.now()
    attempt.save(update_fields=["state", "provider_reference", "last_checked_at", "finalized_at", "updated_at"])
    return True
