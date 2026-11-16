"""Durable pedagogical notifications with the same scope as the parent portal."""
from django.contrib.auth import get_user_model
from django.db.models import Q, F
from .family_notification_models import SchoolFamilyNotification as Notice
from .parent_models import GuardianAccountLink


def visible_notices(user, queryset):
    from .parent_views import guardian_links
    permitted = guardian_links(user).values("guardian__student_id")
    return queryset.filter(Q(student__isnull=True) | Q(student_id__in=permitted, student__school_id=F("school_id")))


def notify_students(school, events, message):
    """Called inside a publication transaction; no external network work here."""
    from .parent_views import guardian_links
    events = list(dict.fromkeys(events))
    if not events or not school.is_active:
        return
    ids = {student for student, _ in events}
    candidates = GuardianAccountLink.objects.filter(school=school, active=True,
        guardian__student_id__in=ids, user__is_active=True, user__is_superuser=False).values_list("user_id", flat=True).distinct()
    rows = []
    for parent in get_user_model().objects.filter(pk__in=candidates):
        allowed = set(guardian_links(parent).filter(school=school, guardian__student_id__in=ids).values_list("guardian__student_id", flat=True))
        rows.extend(Notice(school=school, parent=parent, student_id=student, event_key=key,
            destination=Notice.TO_PARENT, origin="system", message=message)
            for student, key in events if student in allowed)
    Notice.objects.bulk_create(rows, ignore_conflicts=True)
