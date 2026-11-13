"""Confidential school staff remuneration: approved obligations and declared disbursements.

Never mix these payments with tuition cash, or assume a bank/mobile transfer
has been confirmed by an external provider.
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class StaffPayRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT, related_name="staff_payruns")
    staff = models.ForeignKey("institutions.StaffRecord", on_delete=models.PROTECT, related_name="payruns")
    year = models.ForeignKey("institutions.AcademicYear", on_delete=models.PROTECT, related_name="staff_payruns")
    period = models.DateField()
    basis = models.CharField(max_length=20, default="monthly")
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="XAF")
    note = models.CharField(max_length=240, blank=True)
    revision = models.PositiveIntegerField(default=1)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_staff_payruns")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_staff_payruns")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "staff", "period", "basis"], name="uniq_staff_pay_period"),
            models.CheckConstraint(condition=Q(gross_amount__gt=0), name="staff_pay_gross_positive"),
            models.CheckConstraint(condition=Q(deductions__gte=0), name="staff_pay_deductions_nonnegative"),
        ]

    @property
    def net_amount(self):
        return self.gross_amount - self.deductions

    def clean(self):
        if self.staff_id and self.school_id and self.staff.school_id != self.school_id:
            raise ValidationError("Collaborateur d'un autre établissement.")
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("Année scolaire d'un autre établissement.")
        if self.period and self.period.day != 1:
            raise ValidationError("La période doit commencer le premier jour du mois.")
        if self.period and self.year_id and not (
            self.year.start_date <= self.period <= self.year.end_date
        ):
            raise ValidationError("Mois en dehors de l'année scolaire.")
        if self.gross_amount is not None and self.deductions is not None and self.deductions >= self.gross_amount:
            raise ValidationError("Les retenues doivent rester inférieures au montant brut.")
        if self.approved_at and not self.approved_by_id:
            raise ValidationError("Approbateur indépendant requis.")
        if self.approved_by_id and not self.approved_at:
            raise ValidationError("Date d'approbation manquante.")


class StaffPayDisbursement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT, related_name="staff_disbursements")
    pay_run = models.ForeignKey(StaffPayRun, on_delete=models.PROTECT, related_name="disbursements")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20)
    reference = models.CharField(max_length=120)
    paid_on = models.DateField()
    idempotency_key = models.UUIDField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_staff_disbursements")
    recorded_at = models.DateTimeField(auto_now_add=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="voided_staff_disbursements")
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=240, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "idempotency_key"], name="uniq_staff_pay_idempotency"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="staff_disbursement_positive"),
        ]

    def clean(self):
        if self.pay_run_id and self.school_id and self.pay_run.school_id != self.school_id:
            raise ValidationError("Paie d'un autre établissement.")
        if self.method not in ("especes", "virement", "mobile_money", "autre"):
            raise ValidationError("Mode de versement invalide.")
        if not self.reference.strip() or len(self.reference.strip()) > 120:
            raise ValidationError("Justificatif de règlement requis.")
        if bool(self.voided_by_id) != bool(self.voided_at):
            raise ValidationError("Annulation incomplète.")
