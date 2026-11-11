"""Pilotage du propriétaire : synthèse par établissement, en lecture seule.

L'identité de propriétaire (fondateur ou titulaire autorisé) est nécessaire.
Les métriques ne donnent aucune permission de caisse, de gestion pédagogique,
ni accès aux données individuelles des familles ou des salariés.
"""
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.views import authorized
from .academic_models import AcademicClass, AcademicYear
from .assessment_models import Assessment
from .report_models import SchoolReport
from .attendance_models import AttendanceMark
from .admission_models import AdmissionApplication
from .finance_models import FeeCharge, FeePayment
from .models import SchoolAudit, SchoolMember
from .organization_models import SchoolAppointment
from .services import owns_school
from .staff_models import StaffAssignment, StaffRecord
from .student_models import Enrollment
from .cycle_scope import scoped_cycle_ids
from .views import access, refuse


ZERO = Decimal("0.00")
EVENT_LABELS = {
    "student_created": "Fiches élèves créées",
    "student_updated": "Fiches élèves mises à jour",
    "student_enrolled": "Inscriptions d'élèves",
    "staff_created": "Collaborateurs enregistrés",
    "staff_updated": "Fiches du personnel actualisées",
    "staff_dossier_updated": "Fiches professionnelles actualisées",
    "staff_assigned": "Affectations du personnel",
    "role_created": "Rôles créés",
    "role_updated": "Rôles modifiés",
    "member_created": "Comptes créés",
    "admission_created": "Dossiers d'admission créés",
    "admission_decided": "Décisions d'admission",
}


def _money(amount):
    return str((amount or ZERO).quantize(Decimal("0.01")))


@require_GET
@authorized
def owner_overview(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    # Le titre de propriétaire ne devient jamais un accès direct aux opérations.
    if not owns_school(request.user, school):
        return refuse()
    # Compatibilité avec la gouvernance public/privé en cours d'intégration.
    if getattr(school, "governance_mode", "prive_laique") == "public":
        return refuse()
    # Une portée par cycle explicite ne doit pas être contournée par ce rapport global.
    if scoped_cycle_ids(request.user, school) is not None:
        return refuse()

    selected = None
    requested = request.GET.get("year")
    if requested:
        try:
            year_id = UUID(requested)
        except (ValueError, TypeError, AttributeError):
            return JsonResponse({"error": "Année scolaire invalide."}, status=422)
        selected = AcademicYear.objects.filter(school=school, pk=year_id).first()
        if selected is None:
            return JsonResponse({"error": "Année scolaire introuvable."}, status=422)
    else:
        selected = (AcademicYear.objects.filter(school=school, status="current").first()
                    or AcademicYear.objects.filter(school=school, active=True).order_by("-start_date").first()
                    or AcademicYear.objects.filter(school=school).order_by("-start_date").first())

    today = timezone.localdate()
    year_filter = {"year": selected} if selected else {"year__isnull": True}
    classes = AcademicClass.objects.filter(school=school, **year_filter, active=True)
    enrollments = Enrollment.objects.filter(
        school=school, student__school=school, student__active=True,
        active=True, **year_filter,
    )
    applications = AdmissionApplication.objects.filter(school=school, **year_filter)
    classes_by_cycle = list(
        classes.values("level__cycle__name").annotate(total=Count("id")).order_by("level__cycle__name")
    )
    enrolled_by_cycle = dict(
        enrollments.values("classroom__level__cycle__name")
        .annotate(total=Count("student_id", distinct=True))
        .values_list("classroom__level__cycle__name", "total")
    )
    enrollment_by_cycle = [
        {"cycle": item["level__cycle__name"], "classes": item["total"],
         "students": enrolled_by_cycle.get(item["level__cycle__name"], 0)}
        for item in classes_by_cycle
    ]
    for label, quantity in enrolled_by_cycle.items():
        if not any(row["cycle"] == label for row in enrollment_by_cycle):
            enrollment_by_cycle.append({"cycle": label, "classes": 0, "students": quantity})
    enrollment_by_cycle.sort(key=lambda row: row["cycle"] or "")

    admission_counts = dict(
        applications.values("status").annotate(total=Count("id")).values_list("status", "total")
    )
    students = enrollments.values("student_id").distinct().count()
    evaluations = Assessment.objects.filter(
        school=school, course__year=selected, active=True,
    ) if selected else Assessment.objects.none()
    attendance = AttendanceMark.objects.filter(
        school=school, session__classroom__year=selected,
    ) if selected else AttendanceMark.objects.none()
    reports = SchoolReport.objects.filter(
        school=school, year=selected, status="published",
    ) if selected else SchoolReport.objects.none()
    active_staff = StaffRecord.objects.filter(school=school, active=True)
    staff_with_account = active_staff.filter(account__isnull=False).count()
    assigned_staff = (StaffAssignment.objects.filter(
        school=school, active=True, staff__active=True, **year_filter
    ).values("staff_id").distinct().count())

    finance_totals = defaultdict(lambda: {
        "billed": ZERO, "paid": ZERO, "outstanding": ZERO, "overdue": ZERO,
        "paid_this_month": ZERO, "paid_today": ZERO, "payments_today": 0,
    })
    if selected:
        charges = FeeCharge.objects.filter(
            school=school, enrollment__school=school, enrollment__year=selected,
        ).annotate(
            received=Sum("payments__amount", filter=Q(payments__void__isnull=True))
        ).values_list("currency", "amount", "due_date", "received")
        for currency, amount, due_date, received in charges.iterator():
            section = finance_totals[currency]
            outstanding = max(ZERO, amount - (received or ZERO))
            section["billed"] += amount
            section["paid"] += (received or ZERO)
            section["outstanding"] += outstanding
            if due_date and due_date < today:
                section["overdue"] += outstanding

        payments = FeePayment.objects.filter(
            school=school, charge__school=school,
            charge__enrollment__year=selected, void__isnull=True,
        )
        month_start = today.replace(day=1)
        for row in payments.filter(paid_on__gte=month_start, paid_on__lte=today).values("currency").annotate(
            total=Sum("amount")
        ):
            finance_totals[row["currency"]]["paid_this_month"] = row["total"] or ZERO
        for row in payments.filter(paid_on=today).values("currency").annotate(
            total=Sum("amount"), count=Count("id")
        ):
            finance_totals[row["currency"]]["paid_today"] = row["total"] or ZERO
            finance_totals[row["currency"]]["payments_today"] = row["count"]
        monthly_payments = [
            {"month": record["month"].strftime("%Y-%m"),
             "currency": record["currency"], "total": _money(record["total"])}
            for record in payments.filter(
                paid_on__gte=today.replace(day=1) - timedelta(days=185),
                paid_on__lte=today,
            ).annotate(month=TruncMonth("paid_on")).values("month", "currency").annotate(
                total=Sum("amount")
            ).order_by("month", "currency")
        ]
    else:
        monthly_payments = []

    financial_rows = [{
        "currency": currency, "billed": _money(totals["billed"]),
        "paid": _money(totals["paid"]),
        "outstanding": _money(totals["outstanding"]),
        "overdue": _money(totals["overdue"]),
        "paid_this_month": _money(totals["paid_this_month"]),
        "paid_today": _money(totals["paid_today"]),
        "payments_today": totals["payments_today"],
    } for currency, totals in sorted(finance_totals.items())]

    # Tableau d'activité agrégé, sans identifiant, nom, sujet ou détail d'audit.
    start = timezone.now() - timedelta(days=30)
    activity_rows = SchoolAudit.objects.filter(
        school=school, created_at__gte=start,
    ).values("event").annotate(total=Count("id"))
    activities = Counter()
    for row in activity_rows:
        activities[EVENT_LABELS.get(row["event"], "Autres opérations")] += row["total"]
    days = list(SchoolAudit.objects.filter(
        school=school, created_at__gte=start,
    ).annotate(day=TruncDate("created_at")).values("day").annotate(
        total=Count("id")
    ).order_by("-day")[:14])

    return JsonResponse({
        "school": {"id": str(school.pk), "name": school.name, "type": school.school_type},
        "as_of": today.isoformat(),
        "years": [{
            "id": str(y.pk), "name": y.name, "status": y.status,
        } for y in AcademicYear.objects.filter(school=school).order_by("-start_date")[:30]],
        "year": {"id": str(selected.pk), "name": selected.name, "status": selected.status} if selected else None,
        "schooling": {
            "active_students": students,
            "assessments": evaluations.count(),
            "published_assessments": evaluations.filter(published=True).count(),
            "published_reports": reports.count(),
            "absence_marks": attendance.filter(status_group="absent").count(),
            "late_marks": attendance.filter(status_group="late").count(),
            "active_classes": classes.count(),
            "enrollment_by_cycle": enrollment_by_cycle,
            "capacities_defined": classes.filter(capacity__isnull=False).count(),
            "total_defined_places": classes.filter(capacity__isnull=False).aggregate(
                total=Sum("capacity")
            )["total"] or 0,
        },
        "admissions": {
            "total": applications.count(), "pending": sum(
                admission_counts.get(key, 0) for key in ("submitted", "review")
            ),
            "accepted": admission_counts.get("accepted", 0),
            "rejected": admission_counts.get("rejected", 0),
            "enrolled": admission_counts.get("enrolled", 0),
        },
        "staff": {
            "active": active_staff.count(),
            "with_account": staff_with_account,
            "without_account": active_staff.count() - staff_with_account,
            "assigned_to_classes": assigned_staff,
            "active_appointments": SchoolAppointment.objects.filter(
                school=school, staff__active=True, active=True,
            ).filter(Q(starts_on__isnull=True) | Q(starts_on__lte=today)).filter(
                Q(ends_on__isnull=True) | Q(ends_on__gte=today)
            ).count(),
        },
        "finance": {
            "currencies": financial_rows,
            "monthly": monthly_payments,
            "note": "Encaissements enregistrés, hors reçus annulés ; montants distincts par devise.",
        },
        "activity": {
            "total_30d": sum(activities.values()),
            "by_type": [
                {"label": label, "total": count}
                for label, count in activities.most_common(12)
            ],
            "days": [
                {"date": row["day"].isoformat(), "total": row["total"]}
                for row in days
            ],
        },
        "read_only": True,
    }, headers={"Cache-Control": "no-store"})
