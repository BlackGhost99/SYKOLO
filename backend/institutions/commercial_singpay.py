"""Subscription collection: one POST, authenticated evidence, atomic ledger credit."""
from django.db import transaction
from django.utils import timezone
from .models import School
from .commercial_singpay_models import PlatformSingPayMerchant, SubscriptionSingPayIntent as Intent, SubscriptionSingPayEvent as Event
from .singpay_models import SingPayIntent
from .singpay_service import provider_request, verified_transaction, digest, ProviderError
from .subscription_models import PlatformSubscription
from .subscription_views import representation

OPEN = ("initiating", "pending", "unknown", "review", "refund_review")

def initiate(row, merchant):
    payload = {"amount": row.amount_xaf, "reference": row.reference,
               "client_msisdn": row.phone, "portefeuille": row.wallet_id,
               "disbursement": row.disbursement_id, "isTransfer": False}
    try:
        evidence = digest(provider_request(merchant, "POST", "/74/paiement" if row.channel == "airtel" else "/62/paiement", payload))
        state = "pending"
    except ProviderError:
        evidence, state = "", "unknown"
    with transaction.atomic():
        row = Intent.objects.select_for_update().get(pk=row.pk)
        if row.state == "initiating":
            row.state = state
            row.save(update_fields=["state"])
            Event.objects.create(intent=row, kind=state, evidence_hash=evidence)
    return row

def reconcile(row, merchant):
    if not merchant or (row.wallet_id, row.disbursement_id, row.mode, row.merchant_revision) != (merchant.wallet_id, merchant.disbursement_id, merchant.mode, merchant.revision):
        raise ProviderError("Configuration marchande modifiée : contrôle spécialisé requis.")
    response = provider_request(merchant, "GET", "/transaction/api/search/by-reference/" + row.reference)
    with transaction.atomic():
        School.objects.select_for_update().get(pk=row.subscription.year.school_id)
        sub = PlatformSubscription.objects.select_for_update().get(pk=row.subscription_id)
        row = Intent.objects.select_for_update().get(pk=row.pk)
        result = verified_transaction(row, response)
        row.checked_at = timezone.now()
        Event.objects.create(intent=row, kind="verified" if result else "mismatch", evidence_hash=digest(response))
        if row.payment_id or row.state in ("success", "test_success", "refund_review"):
            if not result or result[0] != "success":
                row.state = "refund_review"
        elif row.state != "failed":
            if not result:
                row.state = "review"
            else:
                state, txid = result
                if (Intent.objects.exclude(pk=row.pk).filter(transaction_id=txid).exists()
                        or SingPayIntent.objects.filter(transaction_id=txid).exists()):
                    row.state = "review"
                else:
                    row.state, row.transaction_id = state, txid
                    if state == "success":
                        row.confirmed_at = timezone.now()
                        if row.mode != "live":
                            row.state = "test_success"
                        elif row.amount_xaf > representation(sub)["balance_xaf"]:
                            row.state = "review"
                        else:
                            row.payment = sub.payments.create(reference=row.reference, amount_xaf=row.amount_xaf, method="singpay")
        row.save()
        return row
