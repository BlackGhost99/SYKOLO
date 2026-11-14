"""M3.4: operating expenses, suppliers and approved spending envelopes per school/year.

Not a general ledger: tuition receipts and private staff payroll are separate.
All references use PROTECT to preserve audit history.
"""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class OperatingSupplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    name = models.CharField(max_length=180)
    contact = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class OperatingBudget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    year = models.ForeignKey("institutions.AcademicYear", on_delete=models.PROTECT)
    category = models.CharField(max_length=100)
    currency = models.CharField(max_length=3, default="XAF")
    ceiling = models.DecimalField(max_digits=12, decimal_places=2)
    revision = models.PositiveIntegerField(default=1)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "year", "category", "currency"], name="uniq_yem_operating_budget"),
            models.CheckConstraint(condition=Q(ceiling__gt=0), name="yem_operating_budget_positive"),
        ]

    def clean(self):
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("Année budgétaire d'un autre établissement.")
        if bool(self.approved_by_id) != bool(self.approved_at):
            raise ValidationError("Validation budgétaire incomplète.")


class OperatingExpense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    year = models.ForeignKey("institutions.AcademicYear", on_delete=models.PROTECT)
    budget = models.ForeignKey(OperatingBudget, on_delete=models.PROTECT, related_name="expenses")
    supplier = models.ForeignKey(OperatingSupplier, on_delete=models.PROTECT, related_name="expenses")
    label = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_on = models.DateField()
    invoice_reference = models.CharField(max_length=120)
    revision = models.PositiveIntegerField(default=1)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="yem_operating_expense_positive"),
        ]

    def clean(self):
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("Année de dépense d'un autre établissement.")
        if self.budget_id and self.school_id:
            if self.budget.school_id != self.school_id or self.budget.year_id != self.year_id:
                raise ValidationError("Enveloppe budgétaire étrangère à la dépense.")
        if self.supplier_id and self.school_id and self.supplier.school_id != self.school_id:
            raise ValidationError("Fournisseur d'un autre établissement.")
        if self.year_id and self.expense_on and not self.year.start_date <= self.expense_on <= self.year.end_date:
            raise ValidationError("Dépense en dehors de l'année scolaire.")
        if bool(self.approved_by_id) != bool(self.approved_at):
            raise ValidationError("Validation de dépense incomplète.")


class OperatingExpensePayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    expense = models.ForeignKey(OperatingExpense, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20)
    reference = models.CharField(max_length=120)
    paid_on = models.DateField()
    idempotency_key = models.UUIDField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=240, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "idempotency_key"], name="uniq_yem_expense_payment_key"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="yem_operating_payment_positive"),
        ]

    def clean(self):
        if self.expense_id and self.school_id and self.expense.school_id != self.school_id:
            raise ValidationError("Règlement d'un autre établissement.")
        if self.method not in ("especes", "virement", "mobile_money", "autre"):
            raise ValidationError("Mode de paiement déclaré invalide.")
        if not self.reference.strip():
            raise ValidationError("Justificatif du versement obligatoire.")
        if bool(self.voided_by_id) != bool(self.voided_at):
            raise ValidationError("Annulation de règlement incomplète.")
