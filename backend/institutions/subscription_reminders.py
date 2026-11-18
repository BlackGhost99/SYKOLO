"""Live private commercial reminders derived from the issued subscription ledger.

No delivery outbox or family notifications: these are automatically refreshed
in-app alerts. Stable IDs identify obligations, not repeated notification events.
"""
from datetime import date
from django.db.models import BigIntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from accounts.views import authorized
from .platform_admin_views import denied
from .services import platform_only, school_access
from .subscription_models import PlatformSubscription
from .subscription_pricing import schedule_balances
from .subscription_views import can_consult_commercial
from .subscription_amendments import effective_ledger

REMINDER_WINDOW = 7
PAGE_SIZE = 100


def reminder_rows(row, today):
    result = []
    _, terms = effective_ledger(row)
    for item in schedule_balances(terms, row.paid_xaf, today):
        if not item["balance_xaf"]:
            continue
        due = date.fromisoformat(item["due_date"])
        days = (today - due).days
        if days < -REMINDER_WINDOW:
            continue
        stage = ("due" if days == 0 else "soon" if days < 0 else
                 "late_30" if days >= 30 else "late_7" if days >= 7 else "late")
        result.append({
            "id": f"{row.pk}:{item['kind']}:{item['number']}:{item['due_date']}",
            "subscription_id": row.pk,
            "school_id": str(row.year.school_id), "school": row.year.school.name,
            "year_id": str(row.year_id), "year": row.year.name,
            "kind": item["kind"], "number": item["number"],
            "due_date": item["due_date"], "balance_xaf": item["balance_xaf"],
            "days_until_due": -days, "stage": stage,
        })
    return result


@never_cache
@require_GET
@authorized
def commercial_reminders(request, school_id=None):
    """Read all unpaid contractual due dates, including earlier academic years.

    The school path uses the same authorization as its commercial contracts.
    The central path requires a platform MFA session. No writes or dispatch.
    """
    if school_id is None:
        if not platform_only(request):
            return denied()
    else:
        school = school_access(request.user, school_id)
        if school is None or not can_consult_commercial(request.user, school):
            return denied()
    raw_page = request.GET.get("page", "1")
    if not raw_page.isascii() or not raw_page.isdecimal() or len(raw_page) > 7 or int(raw_page) < 1:
        return JsonResponse({"error": "Page invalide."}, status=422)
    page = int(raw_page)
    today = timezone.localdate()
    query = PlatformSubscription.objects.filter(year__school__is_active=True)
    if school_id is not None:
        query = query.filter(year__school_id=school_id)
    query = query.select_related("year__school").prefetch_related("amendments").annotate(
        paid_xaf=Coalesce(Sum("payments__amount_xaf", filter=Q(payments__voided_at__isnull=True)),
                          Value(0), output_field=BigIntegerField()))
    notices = []
    missing_schedule = 0
    for row in query.iterator(chunk_size=250):
        total_xaf, _ = effective_ledger(row)
        if row.paid_xaf >= total_xaf:
            continue
        if not (row.commercial_terms or {}).get("schedule"):
            missing_schedule += 1
            continue
        notices.extend(reminder_rows(row, today))
    notices.sort(key=lambda item: (item["due_date"], item["school_id"], item["subscription_id"], item["number"]))
    total = len(notices)
    overdue = [item for item in notices if item["days_until_due"] < 0]
    due = [item for item in notices if item["days_until_due"] == 0]
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    return JsonResponse({
        "as_of": today.isoformat(), "window_days": REMINDER_WINDOW,
        "count": total, "overdue_count": len(overdue), "due_count": len(due),
        "upcoming_count": total - len(overdue) - len(due),
        "overdue_xaf": sum(item["balance_xaf"] for item in overdue),
        "missing_schedule_count": missing_schedule,
        "page": page, "pages": pages,
        "reminders": notices[(page-1)*PAGE_SIZE:page*PAGE_SIZE],
    })
