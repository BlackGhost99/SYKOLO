"""Module 11: school-scoped fee schedules and immutable accounting evidence.

This is a MANUAL payment ledger; no transfer, card processing or PSP callback occurs.
"""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .models import School
from .academic_models import AcademicYear, AcademicClass
from .student_models import Enrollment


class FeeSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="fee_schedules")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="fee_schedules")
    classroom = models.ForeignKey(
        AcademicClass, on_delete=models.PROTECT, null=True, blank=True, related_name="fee_schedules"
    )
    scope_key = models.CharField(max_length=36, blank=True)
    code = models.SlugField(max_length=48)
    label = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    due_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "year", "scope_key", "code"],
                name="unique_fee_schedule_per_scope",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="fee_schedule_amount_positive"),
        ]

    def clean(self):
        if self.school_id and self.year_id and self.year.school_id != self.school_id:
            raise ValidationError("L'année scolaire appartient à une autre école.")
        if self.classroom_id and (
            self.classroom.school_id != self.school_id or self.classroom.year_id != self.year_id
        ):
            raise ValidationError("Classe étrangère à l'école ou à l'année.")
        if self.scope_key != (str(self.classroom_id) if self.classroom_id else ""):
            raise ValidationError("Portée tarifaire invalide.")


class FeeCharge(models.Model):
    """Snapshot of an assessed fee. Never changes when the price list changes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="fee_charges")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="fee_charges")
    schedule = models.ForeignKey(FeeSchedule, on_delete=models.PROTECT, related_name="charges")
    label = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "enrollment", "schedule"], name="unique_enrollment_fee_charge"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="fee_charge_amount_positive"),
        ]

    def clean(self):
        if self.enrollment_id and self.school_id and self.enrollment.school_id != self.school_id:
            raise ValidationError("L'inscription appartient à une autre école.")
        if self.schedule_id and self.enrollment_id and (
            self.schedule.school_id != self.school_id
            or self.schedule.year_id != self.enrollment.year_id
            or (self.schedule.classroom_id and self.schedule.classroom_id != self.enrollment.classroom_id)
        ):
            raise ValidationError("Tarif incompatible avec l'inscription.")
        if self.schedule_id and (self.currency != self.schedule.currency or self.amount != self.schedule.amount):
            raise ValidationError("Le montant doit être celui du barème enregistré.")


class FeePaymentBatch(models.Model):
    """One cashier operation split atomically over multiple fees of one enrollment.

    This is a *manual* receipt group; it does not trigger a Mobile Money debit.
    The request hash makes replay with the same key safe and unambiguous.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="payment_batches")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="payment_batches")
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    method = models.SlugField(max_length=48)
    reference = models.CharField(max_length=100, blank=True)
    paid_on = models.DateField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "idempotency_key"], name="unique_school_fee_batch_idempotency"),
            models.CheckConstraint(condition=Q(total__gt=0), name="fee_payment_batch_total_positive"),
        ]

    def clean(self):
        if self.school_id and self.enrollment_id and self.enrollment.school_id != self.school_id:
            raise ValidationError("Inscription étrangère à l'établissement.")


class FeePayment(models.Model):
    """Immutable receipt entry for money manually confirmed by authorized staff."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="fee_payments")
    charge = models.ForeignKey(FeeCharge, on_delete=models.PROTECT, related_name="payments")
    batch = models.ForeignKey(FeePaymentBatch, on_delete=models.PROTECT, related_name="lines", null=True, blank=True)
    idempotency_key = models.UUIDField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    method = models.SlugField(max_length=48)
    reference = models.CharField(max_length=100, blank=True)
    paid_on = models.DateField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "idempotency_key"], name="unique_school_payment_idempotency"),
            models.UniqueConstraint(fields=["batch", "charge"], name="unique_charge_in_fee_batch"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="fee_payment_amount_positive"),
        ]

    def clean(self):
        if self.charge_id and self.school_id and self.charge.school_id != self.school_id:
            raise ValidationError("Encaissement étranger à cette école.")
        if self.charge_id and self.currency != self.charge.currency:
            raise ValidationError("Devise différente de celle du frais.")
        if self.batch_id and (
            self.batch.school_id != self.school_id
            or self.batch.enrollment_id != self.charge.enrollment_id
            or self.batch.currency != self.currency
            or self.batch.method != self.method
            or self.batch.paid_on != self.paid_on
        ):
            raise ValidationError("Ligne incompatible avec le groupe de paiements.")


class FeePaymentVoid(models.Model):
    """One compensating entry per mistaken receipt, no hard delete or alteration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="fee_payment_voids")
    payment = models.OneToOneField(FeePayment, on_delete=models.PROTECT, related_name="void")
    reason = models.TextField(max_length=1000)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.payment_id and self.school_id and self.payment.school_id != self.school_id:
            raise ValidationError("Annulation appartenant à une autre école.")


class CashClosing(models.Model):
    """Immutable declaration of a cashier's physical cash counted on a day.

    Approval is a separate action by a different authorized school member.
    It is independent of any bank or Mobile Money settlement.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="cash_closings")
    day = models.DateField()
    currency = models.CharField(max_length=3)
    expected = models.DecimalField(max_digits=12, decimal_places=2)
    counted = models.DecimalField(max_digits=12, decimal_places=2)
    difference = models.DecimalField(max_digits=13, decimal_places=2)
    note = models.CharField(max_length=500, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="yem_cash_closings_submitted"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="yem_cash_closings_approved",
        null=True, blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_note = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "day", "currency", "submitted_by"],
                name="unique_school_cash_closing_per_cashier",
            ),
            models.CheckConstraint(condition=Q(expected__gte=0), name="cash_closing_expected_nonnegative"),
            models.CheckConstraint(condition=Q(counted__gte=0), name="cash_closing_counted_nonnegative"),
        ]

    def clean(self):
        if self.approved_by_id and self.submitted_by_id == self.approved_by_id:
            raise ValidationError("La caisse ne peut pas être approuvée par son propre déclarant.")


class CashTransfer(models.Model):
    """Documented physical handover or bank deposit, independently checked."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    closing = models.ForeignKey(CashClosing, on_delete=models.PROTECT, related_name="transfers")
    kind = models.CharField(max_length=12, choices=[("handover", "Remise"), ("deposit", "Dépôt")])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100)
    destination = models.CharField(max_length=160)
    day = models.DateField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_transfers_submitted")
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="cash_transfers_approved")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="cash_transfer_positive"),
            models.CheckConstraint(condition=Q(kind__in=["handover", "deposit"]), name="cash_transfer_kind"),
            models.UniqueConstraint(fields=["closing", "kind", "reference"], name="cash_transfer_reference"),
        ]
