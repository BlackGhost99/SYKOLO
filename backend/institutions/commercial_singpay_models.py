"""Platform collections are isolated from school-owned tuition wallets."""
import uuid
from django.conf import settings
from django.db import models

class PlatformSingPayMerchant(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    wallet_id = models.CharField(max_length=120, unique=True)
    disbursement_id = models.CharField(max_length=120)
    encrypted_credentials = models.TextField()
    beneficiary_name = models.CharField(max_length=180)
    contract_reference = models.CharField(max_length=180)
    mode = models.CharField(max_length=8, default="test")
    enabled = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    fee_basis_points = models.PositiveIntegerField(default=0)
    fee_fixed_xaf = models.PositiveIntegerField(default=0)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="singleton_platform_singpay")]

class SubscriptionSingPayIntent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey("institutions.PlatformSubscription", on_delete=models.PROTECT, related_name="singpay_intents")
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    reference = models.CharField(max_length=40, unique=True)
    wallet_id = models.CharField(max_length=120)
    disbursement_id = models.CharField(max_length=120)
    merchant_revision = models.PositiveIntegerField()
    mode = models.CharField(max_length=8)
    beneficiary_name = models.CharField(max_length=180)
    amount_xaf = models.PositiveIntegerField()
    fee_xaf = models.PositiveIntegerField()
    phone = models.CharField(max_length=9)
    channel = models.CharField(max_length=8)
    transaction_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    state = models.CharField(max_length=24, default="initiating")
    payment = models.OneToOneField("institutions.PlatformSubscriptionPayment", on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payer", "idempotency_key"], name="commercial_singpay_idempotency"),
            models.CheckConstraint(condition=models.Q(amount_xaf__gte=100, amount_xaf__lte=10000000), name="commercial_singpay_amount"),
            models.CheckConstraint(condition=models.Q(fee_xaf__lte=models.F("amount_xaf")), name="commercial_singpay_fee"),
        ]

class SubscriptionSingPayEvent(models.Model):
    intent = models.ForeignKey(SubscriptionSingPayIntent, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=40)
    evidence_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
