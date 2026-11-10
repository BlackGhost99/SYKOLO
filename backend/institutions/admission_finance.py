"""Admission payment rules and government scholarships.

Admission approval is NOT payment. A scholarship is independent, approved
evidence of government coverage; it must never create a payment or receipt.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .academic_models import AcademicYear, AcademicLevel
from .admission_models import AdmissionApplication
from .models import School


class AdmissionFinancePolicy(models.Model):
    """Rules per school + year, optionally overridden at level scope."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="admission_finance_rules")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="admission_finance_rules")
    level = models.ForeignKey(AcademicLevel, on_delete=models.PROTECT, null=True, blank=True,
                              related_name="admission_finance_rules")
    scope_key = models.CharField(max_length=80)
    require_payment = models.BooleanField(default=True)
    allow_government_scholarship = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "scope_key"], name="unique_admission_finance_rule_scope"),
        ]

    def clean(self):
        if self.year_id and self.school_id and self.year.school_id != self.school_id:
            raise ValidationError("Année d'un autre établissement.")
        if self.level_id and self.school_id and self.level.school_id != self.school_id:
            raise ValidationError("Niveau d'un autre établissement.")
        if self.year_id and self.scope_key != f"{self.year_id}:{self.level_id or 'all'}":
            raise ValidationError("La portée des frais d'inscription est incohérente.")


class GovernmentScholarship(models.Model):
    """Verified government support. NOT money received or an accounting payment.

    'all' exempts admission and all *future* tuition charges.
    'admission' exempts only the application/admission fee.
    A school administrator must verify the award's official reference.
    """
    COVERAGES = (("all", "Tous les frais"), ("admission", "Frais d'inscription seulement"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="government_scholarships")
    application = models.OneToOneField(AdmissionApplication, on_delete=models.PROTECT,
                                      related_name="government_scholarship")
    coverage = models.CharField(max_length=16, choices=COVERAGES, default="all")
    official_reference = models.CharField(max_length=180)
    active = models.BooleanField(default=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="verified_government_scholarships")
    verified_at = models.DateTimeField(auto_now_add=True)
    revision = models.PositiveIntegerField(default=1)

    def clean(self):
        if self.application_id and self.school_id and self.application.school_id != self.school_id:
            raise ValidationError("Bourse associée à un autre établissement.")
        if self.application_id and self.application.status in ("enrolled", "rejected"):
            # A published student financial arrangement cannot be rewritten
            # through a pre-enrollment scholarship endpoint.
            if self._state.adding:
                raise ValidationError("La décision de bourse doit précéder l'inscription.")
        if not self.official_reference or len(self.official_reference.strip()) < 5:
            raise ValidationError("Référence officielle du document de bourse requise.")
        if self.coverage not in {"all", "admission"}:
            raise ValidationError("Type de prise en charge invalide.")


def policy_scope(year_id, level_id=None):
    return f"{year_id}:{level_id or 'all'}"


def finance_policy(school, year_id, level_id=None):
    """Fail closed for configured institutions, while unclassified legacy pilots
    remain explicitly configurable. All named school cycles default to payable.
    """
    candidates = [policy_scope(year_id, level_id), policy_scope(year_id)]
    for key in dict.fromkeys(candidates):
        policy = AdmissionFinancePolicy.objects.filter(school=school, scope_key=key).first()
        if policy:
            return {
                "require_payment": policy.require_payment,
                "allow_government_scholarship": policy.allow_government_scholarship,
                "scope": key,
                "revision": policy.revision,
                "configured": True,
            }
    return {
        "require_payment": school.school_type != "non_classe" or bool(school.education_cycles),
        "allow_government_scholarship": True,
        "scope": "default",
        "revision": 0,
        "configured": False,
    }


def current_scholarship(application):
    return GovernmentScholarship.objects.filter(
        school_id=application.school_id, application=application, active=True
    ).first()


def scholarship_for_enrollment(enrollment):
    return GovernmentScholarship.objects.filter(
        school_id=enrollment.school_id,
        application__enrollment_id=enrollment.pk,
        application__status="enrolled",
        active=True,
    ).first()


def payment_blocker(application):
    """Return None only after verified settlement, or valid government coverage.

    This check is rerun INSIDE the locked conversion transaction.
    Cash receipt simulations are accepted only in an explicitly enabled pilot,
    never counted as a real payment or as school revenue.
    """
    rule = finance_policy(
        application.school, application.year_id, application.classroom.level_id
    )
    if not rule["require_payment"]:
        return None
    award = current_scholarship(application)
    if award and rule["allow_government_scholarship"]:
        return None
    from .parent_admission_models import ParentAdmissionRequest
    from .parent_payment_models import AdmissionCashReceipt, ParentPaymentAttempt, SchoolDemoPaymentConfig
    link = ParentAdmissionRequest.objects.filter(application=application).first()
    if link is None:
        return ("Frais d'inscription obligatoires : créez une candidature parent avec paiement en "
                "caisse ou faites vérifier une bourse gouvernementale.")
    if not link.fee_amount_xaf:
        return "Configurez d'abord les frais d'inscription de l'année et du niveau."
    if link.payment_choice == "cash":
        receipt = AdmissionCashReceipt.objects.filter(
            request=link, school=application.school, amount_xaf=link.fee_amount_xaf,
            void__isnull=True,
        ).first()
        if receipt:
            if not receipt.is_demo and not link.is_demo_cash:
                return None
            if receipt.is_demo and link.is_demo_cash:
                config = SchoolDemoPaymentConfig.objects.filter(school=application.school, enabled=True).first()
                if config and str(link.owner_id) in config.allowed_parent_ids:
                    return None
        return "Le paiement en espèces doit être validé par la caisse avant l'inscription."
    if ParentPaymentAttempt.objects.filter(
        request=link, school=application.school, amount_xaf=link.fee_amount_xaf,
        state="success", provider_mode="live", currency="XAF",
    ).exists():
        return None
    return "Le paiement en ligne doit être confirmé par le prestataire avant l'inscription."


def direct_enrollment_blocker(school, classroom):
    """Direct student creation/enrollment must not bypass a school's payment rule.

    When payment is mandatory, use an admission application first, even for an
    applicant physically present at the school. Only the admissions conversion
    endpoint verifies the cash receipt or independently approved scholarship.
    """
    rule = finance_policy(school, classroom.year_id, classroom.level_id)
    if rule["require_payment"]:
        return ("Inscription directe désactivée : passez par Admissions et vérifiez "
                "le paiement des frais ou la bourse avant de créer le matricule.")
    return None
