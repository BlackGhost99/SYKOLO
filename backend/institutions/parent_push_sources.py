"""Bridge live admission, payment and due-date alerts into the private push outbox.

Internal rows contain generic text only and never duplicate the visible inbox.
"""
from datetime import datetime, time, timedelta
from django.db.models import F, Q
from django.utils import timezone
from .admission_models import AdmissionEvent
from .finance_models import FeeCharge
from .family_notification_models import SchoolFamilyNotification as Notice
from .parent_payment_models import ParentPaymentAttempt
from .singpay_models import SingPayIntent

PREFIX = "push-source:"
TERMINAL = ("success", "failed", "cancelled", "refunded")
SINGPAY_STATES = ("success", "test_success", "failed", "review", "refund_review")


def singpay_rows(user):
    from .parent_views import guardian_links
    students = guardian_links(user).values("guardian__student_id")
    return SingPayIntent.objects.filter(payer=user, school__is_active=True, state__in=SINGPAY_STATES).filter(
        Q(admission__owner=user, admission__application__school_id=F("school_id"))
        | Q(charge__enrollment__student_id__in=students, charge__school_id=F("school_id"),
            charge__enrollment__school_id=F("school_id"), charge__enrollment__student__school_id=F("school_id"))
    ).select_related("school", "charge__enrollment")


def singpay_notifications(user):
    rows = singpay_rows(user).order_by("-checked_at", "-created_at")[:100]
    return [{
        "id": str(row.pk), "kind": "singpay", "school": row.school.name,
        "status": row.state, "at": (row.checked_at or row.created_at).isoformat(),
        "message": {
            "success": "Paiement SingPay confirmé.",
            "test_success": "Paiement SingPay de simulation, sans règlement réel.",
            "failed": "Paiement SingPay échoué.",
            "review": "Paiement SingPay en cours de vérification.",
            "refund_review": "Paiement SingPay à rapprocher par l’établissement.",
        }[row.state],
    } for row in rows]


def source_events(user, since):
    from .parent_payment_views import unpaid_tuition_notifications
    # Return only source event identity, school and optional protected child.
    events = []
    admissions = AdmissionEvent.objects.filter(
        application__parent_request__owner=user, application__school_id=F("school_id"),
        school__is_active=True, at__gte=since).order_by("-at")[:100]
    events.extend((f"{PREFIX}admission:{e.pk}", e.school_id, None) for e in admissions)
    payments = ParentPaymentAttempt.objects.filter(
        payer=user, request__owner=user, request__application__school_id=F("school_id"),
        school__is_active=True, state__in=TERMINAL, updated_at__gte=since).order_by("-updated_at")[:100]
    events.extend((f"{PREFIX}payment:{p.pk}:{p.state}", p.school_id, None) for p in payments)
    for row in singpay_rows(user).filter(checked_at__gte=since).order_by("-checked_at")[:100]:
        student = row.charge.enrollment.student_id if row.charge_id else None
        events.append((f"{PREFIX}singpay:{row.pk}:{row.state}", row.school_id, student))
    due = {}
    for alert in unpaid_tuition_notifications(user):
        # Existing helper applies verified family links, payments, waivers and due dates.
        _, charge_id, date = alert["id"].split(":")
        day = datetime.fromisoformat(date).date()
        if alert["status"] == "overdue":
            day += timedelta(days=1)  # one overdue transition, never a daily spam
        at = timezone.make_aware(datetime.combine(day, time.min))
        if at >= since:
            due[charge_id] = (alert["id"], alert["status"])
    for charge in FeeCharge.objects.filter(pk__in=due, school__is_active=True).select_related("enrollment"):
        key, state = due[str(charge.pk)]
        events.append((f"{PREFIX}{key}:{state}", charge.school_id, charge.enrollment.student_id))
    return events


def materialize_sources(user, since):
    rows = [Notice(parent=user, school_id=school, student_id=student,
                   destination=Notice.TO_PARENT, origin="system", event_key=key,
                   message="Une nouvelle information est disponible dans votre espace.")
            for key, school, student in source_events(user, since)]
    Notice.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


def source_still_valid(notice, user, since):
    if not notice.event_key.startswith(PREFIX):
        return True
    return (notice.event_key, notice.school_id, notice.student_id) in source_events(user, since)
