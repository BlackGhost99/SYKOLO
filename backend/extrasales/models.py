"""Independent extracurricular sales ledger.

NEVER reuse institutions.FeeCharge/FeePayment (tuition), operating_* (outflows)
or a SingPay callback to record these receipts.
"""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ExtraSale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT, related_name="extra_sales")
    year = models.ForeignKey("institutions.AcademicYear", null=True, blank=True,
                             on_delete=models.PROTECT, related_name="extra_sales")
    reference = models.CharField(max_length=32)
    buyer_label = models.CharField(max_length=120)
    currency = models.CharField(max_length=3)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    catalog_revision = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=80)
    request_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default="confirmed")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="extra_sales_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "reference"], name="extra_sale_school_reference"),
            models.UniqueConstraint(fields=["school", "idempotency_key"], name="extra_sale_school_idempotency"),
            models.CheckConstraint(condition=Q(total__gt=0), name="extra_sale_positive_total"),
        ]


class ExtraSaleLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(ExtraSale, on_delete=models.PROTECT, related_name="lines")
    position = models.PositiveSmallIntegerField()
    catalog_item_id = models.UUIDField()
    code = models.CharField(max_length=30)
    group = models.CharField(max_length=3)
    kind = models.CharField(max_length=12)
    label = models.CharField(max_length=120)
    variant = models.CharField(max_length=80, blank=True)
    unit = models.CharField(max_length=30)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sale", "position"], name="extra_sale_line_position"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="extra_sale_line_positive_qty"),
            models.CheckConstraint(condition=Q(unit_price__gt=0), name="extra_sale_line_positive_unit"),
            models.CheckConstraint(condition=Q(line_total__gt=0), name="extra_sale_line_positive_amount"),
        ]


class ExtraPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(ExtraSale, on_delete=models.PROTECT, related_name="manual_receipts")
    school = models.ForeignKey("institutions.School", on_delete=models.PROTECT,
                               related_name="extra_manual_receipts")
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=24, choices=[
        ("especes", "Espèces"), ("virement", "Virement bancaire"),
    ])
    reference = models.CharField(max_length=120, blank=True)
    evidence = models.CharField(max_length=24, default="manual_declared")
    idempotency_key = models.CharField(max_length=80)
    request_hash = models.CharField(max_length=64)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="extra_manual_receipts_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "idempotency_key"], name="extra_payment_school_idempotency"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="extra_payment_positive_amount"),
        ]
