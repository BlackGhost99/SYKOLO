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
    COVERAGES = (("all", "Tous les frais"), ("admission", "Frais d'inscription seulement"),
                 ("tuition", "Frais de scolarité uniquement"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="government_scholarships")
    application = models.OneToOneField(AdmissionApplication, on_delete=models.PROTECT,
                                      related_name="government_scholarship")
    coverage = models.CharField(max_length=16, choices=COVERAGES, default="all")
    calculation = models.CharField(max_length=10, choices=[("percent", "Pourcentage"), ("fixed", "Montant FCFA")], default="percent")
    percentage = models.PositiveSmallIntegerField(default=100)
    fixed_amount_xaf = models.PositiveIntegerField(null=True, blank=True)
    allocations = models.JSONField(default=dict, blank=True)
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
        if self.coverage not in {"all", "admission", "tuition"}:
            raise ValidationError("Type de prise en charge invalide.")
        if self.calculation == "percent":
            if type(self.percentage) is not int or not 1 <= self.percentage <= 100 or self.fixed_amount_xaf is not None:
                raise ValidationError("Pourcentage de bourse compris entre 1 et 100, sans montant fixe.")
        elif self.calculation == "fixed":
            if type(self.fixed_amount_xaf) is not int or not 1 <= self.fixed_amount_xaf <= 100000000:
                raise ValidationError("Montant de bourse invalide.")
        else:
            raise ValidationError("Mode de calcul de bourse invalide.")


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


def full_admission_waiver(award):
    return bool(award and award.coverage in ("all", "admission")
                and award.calculation == "percent" and award.percentage == 100)


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
    from .admission_scholarship_amounts import admission_due, admission_gross
    if full_admission_waiver(award):
        return None
    if not admission_gross(application):
        return "Configurez d'abord les frais d'inscription de l'année et du niveau."
    # An existing, independently verified award still applies if new awards
    # were disabled later. Partial grants do NOT bypass the remaining balance.
    if award and award.coverage in ("all", "admission") and admission_due(application, award) == 0:
        return None
    from .parent_admission_models import ParentAdmissionRequest
    from .parent_payment_models import AdmissionCashReceipt, ParentPaymentAttempt, SchoolDemoPaymentConfig
    link = ParentAdmissionRequest.objects.filter(application=application).first()
    if link is None:
        # Direct reception at the school is a first-class workflow. It must use
        # the same cashier ledger without manufacturing a parent account.
        due = admission_due(application, award)
        if due < 100:
            return "Solde d'inscription inférieur au minimum encaissable : ajustez la bourse."
        if AdmissionCashReceipt.objects.filter(
            application=application, school=application.school, amount_xaf=due,
            is_demo=False, void__isnull=True,
        ).exists():
            return None
        return "Le paiement en espèces doit être validé dans le module Finances avant l'inscription."
    due = admission_due(application, award)
    if due < 100:
        return "Solde d'inscription inférieur au minimum encaissable : ajustez la bourse."
    if link.payment_choice == "cash":
        receipt = AdmissionCashReceipt.objects.filter(
            request=link, school=application.school, amount_xaf=due,
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
        request=link, school=application.school, amount_xaf=due,
        state="success", provider_mode="live", currency="XAF",
    ).exists():
        return None
    from .singpay_models import SingPayIntent
    if SingPayIntent.objects.filter(
        admission=link, school=application.school, amount_xaf=due,
        state="success", mode="live", confirmed_at__isnull=False,
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
