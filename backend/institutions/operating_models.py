"""M3.4: operating expenses, suppliers and approved spending envelopes per school/year.

Not a general ledger: tuition receipts and private staff payroll are separate.
All references use PROTECT to preserve audit history.
"""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

# Separate the activity served by an expense from its accounting nature.
# Historical expenses are deliberately left unclassified rather than guessed.
ACTIVITY_POLES = (
    ("unclassified", "À classer (historique)"),
    ("school", "Scolarité"),
    ("extraschool", "Extrascolaire"),
    ("common", "Administration et charges communes"),
    ("investment", "Investissements"),
    ("cash_other", "Autres sorties de trésorerie"),
)
ACTIVE_ACTIVITY_POLES = {key for key, _ in ACTIVITY_POLES if key != "unclassified"}

EXPENSE_WORKFLOW_STATES = (
    ("draft", "Brouillon"), ("submitted", "Soumise"),
    ("rejected", "Refusée"), ("approved", "Approuvée"),
)

BENEFICIARY_TYPES = (
    ("supplier", "Fournisseur ou prestataire"),
    ("staff", "Membre du personnel (hors paie)"),
    ("government", "Administration ou organisme public"),
    ("parent", "Parent ou responsable légal"),
    ("individual", "Personne physique"),
    ("organization", "Organisation ou association"),
    ("other", "Autre bénéficiaire"),
)


class OperatingExpenseCategory(models.Model):
    """School-owned two-level catalog; records are archived, never deleted."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="subcategories")
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=100)
    suggested_pole = models.CharField(max_length=20, blank=True, default="",
                                       choices=(("", "Aucun"),) + ACTIVITY_POLES[1:])
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], name="uniq_yem_out_category_code"),
        ]

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.id or self.parent.school_id != self.school_id or self.parent.parent_id:
                raise ValidationError("Une sous-catégorie doit appartenir à une catégorie racine du même établissement.")
            if self.active and not self.parent.active:
                raise ValidationError("Une sous-catégorie active ne peut appartenir à une catégorie archivée.")


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
    # Legacy supplier expenses are preserved. New non-commercial outflows
    # have a named beneficiary without a fabricated supplier record.
    supplier = models.ForeignKey(OperatingSupplier, null=True, blank=True,
                                 on_delete=models.PROTECT, related_name="expenses")
    beneficiary_type = models.CharField(max_length=20, choices=BENEFICIARY_TYPES, default="supplier")
    beneficiary_name = models.CharField(max_length=180, blank=True, default="")
    beneficiary_reference = models.CharField(max_length=120, blank=True, default="")
    # Optional only to preserve historical rows; new expenses require a catalog category.
    category_ref = models.ForeignKey(OperatingExpenseCategory, null=True, blank=True,
                                     on_delete=models.PROTECT, related_name="classified_expenses")
    subcategory_ref = models.ForeignKey(OperatingExpenseCategory, null=True, blank=True,
                                        on_delete=models.PROTECT, related_name="subclassified_expenses")
    category_label_snapshot = models.CharField(max_length=100, blank=True, default="")
    subcategory_label_snapshot = models.CharField(max_length=100, blank=True, default="")
    # Classification de l'activité : indépendante de la catégorie budgétaire.
    activity_pole = models.CharField(max_length=20, choices=ACTIVITY_POLES, default="unclassified")
    cost_center = models.CharField(max_length=100, blank=True, default="")
    accounting_nature = models.CharField(max_length=100, blank=True, default="")
    label = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_on = models.DateField()
    invoice_reference = models.CharField(max_length=120)
    # These states never change the amount committed in the budget.
    # Only approved_at means an authorized budget commitment.
    workflow_state = models.CharField(max_length=12, choices=EXPENSE_WORKFLOW_STATES, default="draft")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    submitted_at = models.DateTimeField(null=True, blank=True)
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
        if self.beneficiary_type not in dict(BENEFICIARY_TYPES):
            raise ValidationError("Type de bénéficiaire invalide.")
        if self.beneficiary_type == "supplier":
            if not self.supplier_id:
                raise ValidationError("Un fournisseur est obligatoire pour ce bénéficiaire.")
        elif self.supplier_id or not self.beneficiary_name.strip():
            raise ValidationError("Indiquez un bénéficiaire nominatif sans fournisseur commercial.")
        if self.category_ref_id:
            if self.category_ref.school_id != self.school_id or self.category_ref.parent_id:
                raise ValidationError("Catégorie de dépenses étrangère ou non principale.")
        if self.subcategory_ref_id:
            if not self.category_ref_id or self.subcategory_ref.school_id != self.school_id or (
                self.subcategory_ref.parent_id != self.category_ref_id
            ):
                raise ValidationError("Sous-catégorie étrangère à la catégorie de dépenses.")
        if self.year_id and self.expense_on and not self.year.start_date <= self.expense_on <= self.year.end_date:
            raise ValidationError("Dépense en dehors de l'année scolaire.")
        if bool(self.approved_by_id) != bool(self.approved_at):
            raise ValidationError("Validation de dépense incomplète.")
        if bool(self.submitted_by_id) != bool(self.submitted_at):
            raise ValidationError("Soumission de dépense incomplète.")
        if self.workflow_state == "submitted" and not self.submitted_at:
            raise ValidationError("Une demande soumise doit conserver son auteur.")
        if self.workflow_state == "approved" and not self.approved_at:
            raise ValidationError("Autorisation de dépense incomplète.")
        if self.approved_at and self.workflow_state != "approved":
            raise ValidationError("Une dépense autorisée ne peut redevenir un projet.")


class OperatingExpenseDecision(models.Model):
    """Append-only workflow evidence, separate from money/payment records."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    expense = models.ForeignKey(OperatingExpense, on_delete=models.PROTECT, related_name="workflow_decisions")
    action = models.CharField(max_length=16, choices=(
        ("submitted", "Soumise"), ("rejected", "Refusée"),
        ("approved", "Approuvée"), ("revised", "Révisée"),
    ))
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    revision = models.PositiveIntegerField()
    reason = models.CharField(max_length=240, blank=True, default="")
    occurred_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.expense_id and self.school_id and self.expense.school_id != self.school_id:
            raise ValidationError("Historique d'une dépense d'un autre établissement.")


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
