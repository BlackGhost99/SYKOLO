"""Single-source scholarship amounts for admission and post-enrollment tuition.

Only the independent approval is a grant; no payment or cash receipt is
created here. Fixed grants are snapshotted per tariff at approval time so
subsequent price changes do not silently increase the taxpayer's commitment.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q


def xaf(value):
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def admission_gross(application):
    from .parent_admission_models import ParentAdmissionRequest
    from .parent_payment_models import SchoolAdmissionFee
    parent = ParentAdmissionRequest.objects.filter(application=application).first()
    if parent:
        if parent.fee_amount_xaf:
            return parent.fee_amount_xaf
        if parent.payment_choice != "cash" or parent.is_demo_cash:
            return 0
    elif application.admission_fee_snapshot_xaf is not None:
        return application.admission_fee_snapshot_xaf
    fee = SchoolAdmissionFee.objects.filter(
        school_id=application.school_id, year_id=application.year_id,
        level_id=application.classroom.level_id, active=True,
    ).first()
    return fee.amount_xaf if fee else 0


def tuition_schedules(application):
    from .finance_models import FeeSchedule
    return list(FeeSchedule.objects.filter(
        school_id=application.school_id, year_id=application.year_id,
        active=True, currency="XAF",
    ).filter(Q(classroom__isnull=True) |
             Q(classroom_id=application.classroom_id)).order_by("due_date", "pk"))


def calculate_award(application, *, coverage, calculation, percentage=100, fixed_amount_xaf=None):
    """Snapshot for a new approval. Amounts are XAF integers, never money received."""
    gross = admission_gross(application)
    schedules = tuition_schedules(application)
    grant_admission = coverage in ("all", "admission")
    grant_tuition = coverage in ("all", "tuition")
    if calculation == "fixed":
        eligible = (gross if grant_admission else 0) + sum(xaf(s.amount) for s in schedules if grant_tuition)
        if not eligible:
            raise ValueError("Configurez les frais concernés avant d'attribuer un montant fixe.")
        if int(fixed_amount_xaf) > eligible:
            raise ValueError("La prise en charge fixe dépasse le montant des frais concernés.")
        budget = int(fixed_amount_xaf)
        admission_covered = min(budget, gross) if grant_admission else 0
        budget -= admission_covered
        tuition = {}
        for schedule in schedules if grant_tuition else []:
            covered = min(budget, xaf(schedule.amount))
            if covered:
                tuition[str(schedule.pk)] = covered
            budget -= covered
    else:
        admission_covered = xaf(Decimal(gross) * Decimal(percentage) / 100) if grant_admission else 0
        tuition = {
            str(s.pk): min(xaf(s.amount), xaf(s.amount * Decimal(percentage) / 100))
            for s in schedules if grant_tuition
        }
    return {"admission": admission_covered, "tuition": tuition}


def admission_due(application, award=None):
    from .admission_finance import current_scholarship
    award = award if award is not None else current_scholarship(application)
    gross = admission_gross(application)
    if not award or award.coverage not in ("all", "admission"):
        return gross
    covered = (xaf(Decimal(gross) * Decimal(award.percentage) / 100)
               if award.calculation == "percent" else
               int((award.allocations or {}).get("admission", 0)))
    return max(0, gross - min(gross, int(covered)))


def tuition_discount(enrollment, schedule):
    from .admission_finance import scholarship_for_enrollment
    award = scholarship_for_enrollment(enrollment)
    if not award or award.coverage not in ("all", "tuition") or schedule.currency != "XAF":
        return Decimal("0.00")
    if award.calculation == "percent":
        covered = xaf(schedule.amount * Decimal(award.percentage) / 100)
    else:
        covered = (award.allocations or {}).get("tuition", {}).get(str(schedule.pk), 0)
    return min(schedule.amount, Decimal(covered).quantize(Decimal("0.01")))


def tuition_discount_for_application(award, schedule):
    if award.coverage not in ("all", "tuition") or schedule.currency != "XAF":
        return Decimal("0.00")
    if award.calculation == "percent":
        return min(schedule.amount, Decimal(xaf(schedule.amount * Decimal(award.percentage) / 100)))
    return min(schedule.amount, Decimal((award.allocations or {}).get("tuition", {}).get(str(schedule.pk), 0)))


def grant_summary(application, award=None):
    from .admission_finance import current_scholarship
    award = award if award is not None else current_scholarship(application)
    gross_admission = admission_gross(application)
    schedules = tuition_schedules(application)
    gross_tuition = sum(xaf(s.amount) for s in schedules)
    admission_covered = gross_admission - admission_due(application, award) if award else 0
    tuition_covered = sum(
        xaf(tuition_discount_for_application(award, s)) for s in schedules
    ) if award else 0
    return {
        "admission_gross_xaf": gross_admission,
        "admission_scholarship_xaf": admission_covered,
        "admission_due_xaf": gross_admission-admission_covered,
        "tuition_gross_xaf": gross_tuition,
        "tuition_scholarship_xaf": tuition_covered,
        "tuition_due_xaf": gross_tuition-tuition_covered,
        "total_due_xaf": gross_admission+gross_tuition-admission_covered-tuition_covered,
    }
