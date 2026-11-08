"""School-year closure readiness and immutable annual statistics.

This module deliberately exposes a preview even while final closure is gated.
Never silently close draft assessments, sessions, councils or unresolved payments.
"""
import hashlib
import json
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from .academic_models import AcademicClass, AcademicPeriod
from .assessment_models import Assessment, AssessmentGrade
from .attendance_models import AttendanceSession, AttendanceMark
from .council_models import SchoolCouncil, CouncilDecision
from .curriculum_models import CourseOffering
from .finance_models import (
    FeeCharge, FeePayment, CashClosing, CashTransfer,
)
from .parent_payment_models import ParentPaymentAttempt
from .report_models import SchoolReport
from .singpay_models import SingPayIntent
from .staff_models import StaffAssignment
from .student_models import Enrollment


def annual_closure_snapshot(school, year):
    """Deterministic totals suitable for an audited closure record."""
    enrolled = Enrollment.objects.filter(school=school, year=year)
    rooms = AcademicClass.objects.filter(school=school, year=year)
    assignments = StaffAssignment.objects.filter(school=school, year=year)
    assessments = Assessment.objects.filter(school=school, course__year=year)
    published = SchoolReport.objects.filter(school=school, year=year, status="published")
    charges = FeeCharge.objects.filter(school=school, enrollment__year=year)
    payments = FeePayment.objects.filter(
        school=school, charge__enrollment__year=year, void__isnull=True
    )
    currencies = sorted(set(charges.values_list("currency", flat=True)) |
                        set(payments.values_list("currency", flat=True)))
    ledger = {}
    for currency in currencies:
        billed = charges.filter(currency=currency).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        paid = payments.filter(currency=currency).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        ledger[currency] = {
            "billed": str(billed), "received": str(paid), "outstanding": str(billed - paid),
        }
    by_class = []
    for room in rooms.select_related("level", "level__cycle").order_by("level__order", "name", "pk"):
        by_class.append({
            "id": str(room.pk), "name": room.name,
            "level": room.level.name, "cycle": room.level.cycle.name,
            "enrollments": enrolled.filter(classroom=room).count(),
            "assigned_staff": assignments.filter(classroom=room).values("staff_id").distinct().count(),
            "published_reports": published.filter(enrollment__classroom=room).count(),
        })
    return {
        "version": 1,
        "school_id": str(school.pk),
        "year_id": str(year.pk),
        "year_name": year.name,
        "period": {"start": year.start_date.isoformat(), "end": year.end_date.isoformat()},
        "counts": {
            "classes": rooms.count(),
            "periods": AcademicPeriod.objects.filter(school=school, year=year).count(),
            "enrollments": enrolled.count(),
            "students": enrolled.values("student_id").distinct().count(),
            "staff_assignments": assignments.count(),
            "staff_members_assigned": assignments.values("staff_id").distinct().count(),
            "courses": CourseOffering.objects.filter(school=school, year=year).count(),
            "assessments": assessments.count(),
            "grades": AssessmentGrade.objects.filter(school=school, assessment__course__year=year).count(),
            "published_reports": published.count(),
            "attendance_sessions": AttendanceSession.objects.filter(school=school, classroom__year=year).count(),
            "attendance_marks": AttendanceMark.objects.filter(school=school, session__classroom__year=year).count(),
            "councils": SchoolCouncil.objects.filter(school=school, year=year).count(),
            "council_decisions": CouncilDecision.objects.filter(school=school, council__year=year).count(),
        },
        "classes": by_class,
        "finance": ledger,
    }


def closure_fingerprint(snapshot):
    return hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def annual_closure_checks(school, year):
    """Hard blockers and warnings, always recomputed inside the closing transaction."""
    blockers, warnings = [], []
    if year.status != year.STATUS_CURRENT or not year.active:
        blockers.append({"code": "not_current", "message": "Seule l'année en cours peut être clôturée."})
    if timezone.localdate() < year.end_date:
        blockers.append({"code": "year_not_finished", "message": "La date de fin de l'année n'est pas atteinte."})

    unresolved = [
        ("draft_assessments", "Des évaluations ne sont pas publiées.",
         Assessment.objects.filter(school=school, course__year=year, active=True, published=False).count()),
        ("draft_reports", "Des bulletins sont encore en brouillon.",
         SchoolReport.objects.filter(school=school, year=year, status="draft").count()),
        ("open_councils", "Des conseils de classe ne sont pas clos.",
         SchoolCouncil.objects.filter(school=school, year=year).exclude(status="closed").count()),
        ("open_attendance", "Des séances de présence sont non clôturées.",
         AttendanceSession.objects.filter(school=school, classroom__year=year, closed_at__isnull=True).count()),
        ("pending_singpay", "Des opérations SingPay demandent un rapprochement.",
         SingPayIntent.objects.filter(school=school, state__in=[
             "initiating", "pending", "unknown", "review", "refund_review",
         ]).filter(Q(charge__enrollment__year=year) |
                  Q(admission__application__year=year)).count()),
        ("pending_parent_payments", "Des paiements parents sont non confirmés.",
         ParentPaymentAttempt.objects.filter(
             school=school, request__application__year=year,
             state__in=["initiating", "pending", "unknown"],
         ).count()),
        ("pending_cash_approvals", "Des clôtures de caisse attendent validation.",
         CashClosing.objects.filter(
             school=school, day__gte=year.start_date, day__lte=year.end_date,
             approved_at__isnull=True,
         ).count()),
        ("pending_cash_transfers", "Des remises ou dépôts attendent validation.",
         CashTransfer.objects.filter(
             closing__school=school, closing__day__gte=year.start_date,
             closing__day__lte=year.end_date, approved_at__isnull=True,
         ).count()),
    ]
    for code, label, count in unresolved:
        if count:
            blockers.append({"code": code, "message": label, "count": count})
    if not AcademicPeriod.objects.filter(school=school, year=year).exists():
        warnings.append({"code": "no_periods", "message": "Aucune période pédagogique n'est configurée."})
    if not Enrollment.objects.filter(school=school, year=year).exists():
        warnings.append({"code": "no_enrollments", "message": "Aucun élève n'est inscrit pour cette année."})
    return {"ready": not blockers, "blockers": blockers, "warnings": warnings}
