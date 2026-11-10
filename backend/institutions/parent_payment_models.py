"""Payment configuration and immutable-attempt snapshots for pre-enrollment.

This ledger is NOT the tuition ledger. An admission payment never creates an
official Enrollment or a FeePayment, even after a verified gateway success.
"""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .models import School
from .academic_models import AcademicYear, AcademicLevel
from .parent_admission_models import ParentAdmissionRequest


class SchoolAdmissionFee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="parent_admission_fees")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="parent_admission_fees")
    level = models.ForeignKey(AcademicLevel, on_delete=models.PROTECT, related_name="parent_admission_fees")
    amount_xaf = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "year", "level"], name="unique_parent_admission_fee_scope"),
            models.CheckConstraint(condition=Q(amount_xaf__gte=100, amount_xaf__lte=10000000), name="parent_admission_fee_range"),
        ]
    def clean(self):
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("Année étrangère à l'établissement.")
        if self.level_id and self.school_id and self.level.school_id != self.school_id:
            raise ValidationError("Niveau étranger à l'établissement.")


class SchoolPaymentGateway(models.Model):
    """Keys are encrypted at rest, never returned by an API, and scoped to ONE school."""
    school = models.OneToOneField(School, primary_key=True, on_delete=models.PROTECT, related_name="admission_gateway")
    provider = models.CharField(max_length=24, default="paycentral")
    mode = models.CharField(max_length=8, choices=[("sandbox", "Simulation"), ("live", "Production")], default="sandbox")
    encrypted_api_key = models.TextField(blank=True)
    encrypted_webhook_secret = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class ParentPaymentAttempt(models.Model):
    STATES = [
        ("initiating", "En cours d'initiation"),
        ("pending", "En attente de confirmation"),
        ("unknown", "À rapprocher"),
        ("success", "Confirmé par le prestataire"),
        ("failed", "Échoué"),
        ("cancelled", "Annulé"),
        ("refunded", "Remboursé"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ParentAdmissionRequest, on_delete=models.PROTECT, related_name="payment_attempts")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="parent_payment_attempts")
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="parent_payment_attempts")
    amount_xaf = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="XAF")
    provider = models.CharField(max_length=24, default="paycentral")
    provider_mode = models.CharField(max_length=8, default="sandbox")
    channel = models.CharField(max_length=16, choices=[("airtel", "Airtel Money"), ("moov", "Moov Money")])
    payer_phone = models.CharField(max_length=24)
    merchant_reference = models.CharField(max_length=48, unique=True)
    transaction_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    state = models.CharField(max_length=16, choices=STATES, default="initiating")
    provider_reference = models.CharField(max_length=140, blank=True)
    last_checked_at = models.DateTimeField(blank=True, null=True)
    finalized_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=["school", "state"], name="yem_parentpay_school_state")]
        constraints = [
            models.CheckConstraint(condition=Q(amount_xaf__gte=100, amount_xaf__lte=10000000), name="parent_payment_amount_range"),
        ]
    def clean(self):
        if self.request_id and self.school_id and self.request.application.school_id != self.school_id:
            raise ValidationError("Paiement incompatible avec l'établissement.")
        if self.request_id and self.payer_id and self.request.owner_id != self.payer_id:
            raise ValidationError("Paiement incompatible avec le compte parent.")



class SchoolDemoPaymentConfig(models.Model):
    """Explicit no-money rehearsal, restricted to named fictitious parent accounts.

    It never represents a merchant payment, fee receipt, tuition settlement, or
    actual money transfer. Amounts are isolated from admission fee tariffs.
    """
    school = models.OneToOneField(
        School, primary_key=True, on_delete=models.PROTECT,
        related_name="demo_admission_config",
    )
    enabled = models.BooleanField(default=False)
    # Key: "<year UUID>:<level UUID>" ; value: example amount in XAF.
    level_amounts_xaf = models.JSONField(default=dict, blank=True)
    allowed_parent_ids = models.JSONField(default=list, blank=True)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not isinstance(self.level_amounts_xaf, dict) or len(self.level_amounts_xaf) > 150:
            raise ValidationError("Configuration des montants simulés invalide.")
        for key, amount in self.level_amounts_xaf.items():
            parts = key.split(":") if isinstance(key, str) else []
            if len(parts) != 2:
                raise ValidationError("Année ou niveau de simulation invalide.")
            try:
                year_id, level_id = uuid.UUID(parts[0]), uuid.UUID(parts[1])
            except ValueError:
                raise ValidationError("Identifiant de montant simulé invalide.")
            if not isinstance(amount, int) or isinstance(amount, bool) or not 100 <= amount <= 10000000:
                raise ValidationError("Montant simulé hors des limites.")
            if not AcademicYear.objects.filter(school_id=self.school_id, pk=year_id).exists():
                raise ValidationError("Année de simulation étrangère à l'école.")
            if not AcademicLevel.objects.filter(school_id=self.school_id, pk=level_id).exists():
                raise ValidationError("Niveau de simulation étranger à l'école.")
        if not isinstance(self.allowed_parent_ids, list) or len(self.allowed_parent_ids) > 50:
            raise ValidationError("Liste de comptes parents tests invalide.")
        if len(self.allowed_parent_ids) != len(set(self.allowed_parent_ids)):
            raise ValidationError("Compte de test en double.")
        for user_id in self.allowed_parent_ids:
            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError, AttributeError):
                raise ValidationError("Compte parent de test invalide.")


class AdmissionCashReceipt(models.Model):
    """Confirmation at school counter, entirely separate from PSP/tuition ledger.

    is_demo=True is NOT a financial receipt and must never enter daily cash totals.
    It cannot be turned into real cash after recording.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(
        ParentAdmissionRequest, on_delete=models.PROTECT, related_name="cash_receipt",
    )
    school = models.ForeignKey(
        School, on_delete=models.PROTECT, related_name="admission_cash_receipts",
    )
    amount_xaf = models.PositiveIntegerField()
    is_demo = models.BooleanField(default=False)
    reference = models.CharField(max_length=100, blank=True)
    received_on = models.DateField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_xaf__gte=100, amount_xaf__lte=10000000),
                name="admission_cash_receipt_amount_valid",
            ),
        ]

    def clean(self):
        if self.request_id and self.school_id:
            if self.request.application.school_id != self.school_id:
                raise ValidationError("Paiement rattaché à un autre établissement.")
            if self.request.payment_choice != "cash":
                raise ValidationError("Le parent n'a pas choisi les espèces.")
            if self.request.fee_amount_xaf != self.amount_xaf:
                raise ValidationError("Montant différent du tarif accepté lors de la candidature.")
            if self.request.is_demo_cash != self.is_demo:
                raise ValidationError("La simulation ne peut pas être convertie en argent réel.")


class AdmissionCashReceiptVoid(models.Model):
    """Independent corrective evidence; the original cash receipt is immutable."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.OneToOneField(
        AdmissionCashReceipt, on_delete=models.PROTECT, related_name="void",
    )
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.receipt_id and self.school_id and self.receipt.school_id != self.school_id:
            raise ValidationError("Annulation liée à un autre établissement.")
        if self.receipt_id and self.voided_by_id == self.receipt.recorded_by_id:
            raise ValidationError("Un autre responsable doit annuler l'enregistrement.")
