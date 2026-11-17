"""Commercial YEM subscriptions, separate from school tuition."""
from django.conf import settings
from django.db import models
from .academic_models import AcademicYear


class PlatformSubscription(models.Model):
    year = models.OneToOneField(AcademicYear, on_delete=models.PROTECT, related_name="platform_subscription")
    lines = models.JSONField()
    total_xaf = models.PositiveBigIntegerField()
    commercial_terms = models.JSONField(default=dict, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")


class PlatformSubscriptionPayment(models.Model):
    subscription = models.ForeignKey(PlatformSubscription, on_delete=models.PROTECT, related_name="payments")
    reference = models.CharField(max_length=100)
    amount_xaf = models.PositiveBigIntegerField()
    method = models.CharField(max_length=24)
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=240, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["subscription", "reference"], name="unique_yem_subscription_payment_ref"),
            models.CheckConstraint(condition=models.Q(amount_xaf__gt=0), name="positive_yem_subscription_payment"),
        ]


class PlatformSubscriptionPolicy(models.Model):
    """One global versioned tariff; historical contracts keep their own terms."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    rates = models.JSONField(default=dict)
    minimums = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="singleton_yem_subscription_policy")]
