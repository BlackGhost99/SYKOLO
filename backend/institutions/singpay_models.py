"""School-owned merchant accounts and immutable payment evidence.

Separate from PayCentral admission attempts; no migration of historical money.
"""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class SingPayMerchant(models.Model):
    school = models.OneToOneField("institutions.School", on_delete=models.PROTECT, primary_key=True)
    wallet_id = models.CharField(max_length=120, unique=True)
    disbursement_id = models.CharField(max_length=120)
    encrypted_credentials = models.TextField()
    beneficiary_name = models.CharField(max_length=180)
    contract_reference = models.CharField(max_length=180)
    mode = models.CharField(max_length=8, choices=[("test", "Test prestataire"), ("live", "Production")], default="test")
    enabled = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    # Contractual fee, absorbed by school. Never invent a provider tariff.
    fee_basis_points = models.PositiveIntegerField(default=0)
    fee_fixed_xaf = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class SingPayIntent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    charge = models.ForeignKey("institutions.FeeCharge", null=True, blank=True, on_delete=models.PROTECT)
    admission = models.ForeignKey("institutions.ParentAdmissionRequest", null=True, blank=True, on_delete=models.PROTECT)
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
    payment = models.OneToOneField("institutions.FeePayment", null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payer", "idempotency_key"], name="singpay_payer_idempotency"),
            models.CheckConstraint(condition=(Q(charge__isnull=False, admission__isnull=True) | Q(charge__isnull=True, admission__isnull=False)), name="singpay_one_obligation"),
            models.CheckConstraint(condition=Q(amount_xaf__gte=100, amount_xaf__lte=10000000), name="singpay_amount_range"),
            models.CheckConstraint(condition=Q(fee_xaf__lte=models.F("amount_xaf")), name="singpay_fee_limit"),
        ]
        indexes = [models.Index(fields=["school", "state"], name="singpay_school_state")]


class SingPayEvent(models.Model):
    intent = models.ForeignKey(SingPayIntent, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=40)
    # Hash of evidence only: never persist raw responses, credentials or phone in logs.
    evidence_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SingPaySettlement(models.Model):
    """Documentary merchant settlement, independently approved; never moves funds."""
    intent = models.OneToOneField(SingPayIntent, on_delete=models.PROTECT, primary_key=True)
    statement_reference = models.CharField(max_length=180)
    received_net_xaf = models.PositiveIntegerField()
    observed_fee_xaf = models.PositiveIntegerField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="singpay_settlements_submitted")
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="singpay_settlements_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
