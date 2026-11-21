"""B3 — Demandes scolaires avant engagement.

Une demande de personnel n'est PAS une OperatingExpense, une dette ou un
décaissement. La conversion contrôlée en engagement relève de B5.
"""
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .operating_models import (
    OperatingExpenseCategory, OperatingSupplier, OperatingClassificationOption,
)

SCHOOL_REQUEST_STATES = (
    ("draft", "Brouillon"),
    ("submitted", "Soumise"),
    ("in_review", "En examen"),
    ("approved", "Validée pour instruction budgétaire"),
    ("rejected", "Refusée"),
    ("cancelled", "Annulée"),
)
SCHOOL_REQUEST_URGENCY = (
    ("normal", "Normale"), ("high", "Prioritaire"), ("critical", "Urgente"),
)


class OperatingSchoolRequest(models.Model):
    """School-only purchasing need, outside every financial aggregate."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    year = models.ForeignKey("institutions.AcademicYear", on_delete=models.PROTECT)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requester_function = models.CharField(max_length=120)
    service = models.CharField(max_length=120)
    reason = models.CharField(max_length=600)
    category = models.ForeignKey(OperatingExpenseCategory, on_delete=models.PROTECT, related_name="+")
    subcategory = models.ForeignKey(
        OperatingExpenseCategory, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    category_snapshot = models.CharField(max_length=100)
    subcategory_snapshot = models.CharField(max_length=100, blank=True, default="")
    cost_center = models.ForeignKey(
        OperatingClassificationOption, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cost_center_snapshot = models.CharField(max_length=100, blank=True, default="")
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    estimated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="XAF")
    supplier = models.ForeignKey(OperatingSupplier, null=True, blank=True,
                                  on_delete=models.PROTECT, related_name="+")
    beneficiary_name = models.CharField(max_length=180)
    urgency = models.CharField(max_length=12, choices=SCHOOL_REQUEST_URGENCY, default="normal")
    desired_on = models.DateField()
    supporting_reference = models.CharField(max_length=240, blank=True, default="")
    status = models.CharField(max_length=12, choices=SCHOOL_REQUEST_STATES, default="draft")
    revision = models.PositiveIntegerField(default=1)
    idempotency_key = models.UUIDField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "idempotency_key"],
                                    name="uniq_yem_school_request_key"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="yem_school_request_quantity_positive"),
            models.CheckConstraint(condition=Q(estimated_amount__gt=0), name="yem_school_request_amount_positive"),
            models.CheckConstraint(condition=(
                Q(estimated_unit_price__isnull=True) | Q(estimated_unit_price__gt=0)
            ), name="yem_school_request_unit_price_positive"),
        ]

    def clean(self):
        if self.school_id and self.year_id and self.year.school_id != self.school_id:
            raise ValidationError("Année d'un autre établissement.")
        if self.school_id and self.category_id:
            if self.category.school_id != self.school_id or self.category.parent_id:
                raise ValidationError("Catégorie de demande invalide ou étrangère.")
        if self.subcategory_id and (
            not self.category_id or self.subcategory.school_id != self.school_id
            or self.subcategory.parent_id != self.category_id
        ):
            raise ValidationError("Sous-catégorie étrangère au dossier.")
        if self.supplier_id and self.supplier.school_id != self.school_id:
            raise ValidationError("Fournisseur d'un autre établissement.")
        if self.cost_center_id:
            center = self.cost_center
            if center.school_id != self.school_id or center.kind != "cost_center" or (
                center.activity_pole not in ("", "school")
            ):
                raise ValidationError("Centre de coûts scolaire invalide ou étranger.")
        if self.year_id and self.desired_on and not (
            self.year.start_date <= self.desired_on <= self.year.end_date
        ):
            raise ValidationError("Date souhaitée hors de l'année scolaire.")
        if self.estimated_unit_price is not None and self.quantity is not None and self.estimated_amount is not None:
            estimated = (self.estimated_unit_price * self.quantity).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if estimated != self.estimated_amount:
                raise ValidationError("Quantité × prix unitaire doit égaler le montant estimé.")
        if self.status not in dict(SCHOOL_REQUEST_STATES):
            raise ValidationError("Statut de demande inconnu.")
        if self.status in ("submitted", "in_review", "approved") and not self.submitted_at:
            raise ValidationError("Soumission sans horodatage.")
        if bool(self.reviewed_by_id) != bool(self.reviewed_at):
            raise ValidationError("Examen incomplet.")
        if bool(self.decided_by_id) != bool(self.decided_at):
            raise ValidationError("Décision incomplète.")


class OperatingSchoolRequestEvent(models.Model):
    """Historique append-only des étapes, sans montant dans SchoolAudit."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT)
    request = models.ForeignKey(OperatingSchoolRequest, on_delete=models.PROTECT,
                                related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=20, choices=(
        ("submitted", "Soumise"), ("in_review", "En examen"),
        ("approved", "Validée"), ("rejected", "Refusée"),
        ("revised", "Révisée"), ("cancelled", "Annulée"),
    ))
    revision = models.PositiveIntegerField()
    reason = models.CharField(max_length=500, blank=True, default="")
    happened_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.request_id and self.school_id and self.request.school_id != self.school_id:
            raise ValidationError("Événement d'un autre établissement.")
