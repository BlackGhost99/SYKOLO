"""Commercial lifecycle and explicit school workspace read-only restrictions.

Expiry and late payments never change a school's activation or access by themselves.
"""
from datetime import date, timedelta
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .models import School
from .services import platform_only, school_access
from .platform_admin_views import audit, denied
from .subscription_models import PlatformSubscription, PlatformCommercialAccessDecision
from .subscription_amendments import effective_ledger, trial_summary
from .subscription_pricing import add_months, schedule_balances
from .views import parse_body


GRACE_DAYS = 30


def last_decision(school):
    return PlatformCommercialAccessDecision.objects.filter(school=school).order_by("-revision").first()


def commercial_status(school, today):
    contracts = PlatformSubscription.objects.filter(year__school=school).prefetch_related("payments", "amendments")
    active = False
    future = False
    expired = False
    unknown = False
    overdue = 0
    late_30 = 0
    next_end = None
    last_expiry = None
    first_overdue = None
    next_due = None
    due_today = False
    for row in contracts:
        try:
            total, terms = effective_ledger(row)
            paid = sum(p.amount_xaf for p in row.payments.all() if p.voided_at is None)
            schedule = terms.get("schedule", [])
            identities = [(s["kind"], s["number"]) for s in schedule]
            initial = [s for s in (row.commercial_terms or {}).get("schedule", []) if s["kind"] == "abonnement"]
            if (not initial or not schedule or len(set(identities)) != len(identities)
                or any(type(s["amount_xaf"]) is not int or s["amount_xaf"] < 0 for s in schedule)
                or sum(s["amount_xaf"] for s in schedule) != total):
                raise ValueError("Invalid schedule")
            start = date.fromisoformat(initial[0]["due_date"])
            end = add_months(start, 12)
            balances = schedule_balances(terms, paid, today)
        except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
            unknown = True
            continue
        if start <= today < end:
            active = True
            next_end = max(next_end or end, end)
        elif today < start:
            future = True
        else:
            expired = True
            last_expiry = max(last_expiry or end, end)
        for item in balances:
            if not item["balance_xaf"]:
                continue
            due = date.fromisoformat(item["due_date"])
            if item["days_overdue"]:
                overdue += item["balance_xaf"]
                first_overdue = min(first_overdue or due, due)
            else:
                next_due = min(next_due or due, due)
                due_today = due_today or due == today
            if item["days_overdue"] >= GRACE_DAYS:
                late_30 += item["balance_xaf"]
    trial = trial_summary(school, today)
    if active:
        lifecycle = "active"
    elif trial and trial["status"] == "active":
        lifecycle = "trial_active"
    elif unknown:
        lifecycle = "review"
    elif future:
        lifecycle = "scheduled"
    elif expired or (trial and trial["status"] == "expired"):
        lifecycle = "expired"
    else:
        lifecycle = "unconfigured"
    # The trial ending is not an authorization to start charging or sanctioning.
    # Only an issued paid contract can start the commercial grace countdown.
    grace_deadlines = []
    if first_overdue:
        grace_deadlines.append(first_overdue + timedelta(days=GRACE_DAYS))
    if lifecycle == "expired" and last_expiry:
        grace_deadlines.append(last_expiry + timedelta(days=GRACE_DAYS))
    eligible_on = min(grace_deadlines) if grace_deadlines else None
    decision = last_decision(school)
    return {"lifecycle": lifecycle, "billing_started": bool(contracts), "service_ends_before": next_end.isoformat() if next_end else None,
            "next_payment_due": next_due.isoformat() if next_due else None,
            "oldest_overdue_on": first_overdue.isoformat() if first_overdue else None,
            "payment_due_today": due_today, "schedule_review": unknown,
            "last_service_ended_on": last_expiry.isoformat() if last_expiry else None,
            "overdue_xaf": overdue, "late_30_xaf": late_30,
            "restricted": bool(decision and decision.restricted),
            "revision": decision.revision if decision else 0,
            "grace_days": GRACE_DAYS,
            "restriction_eligible_on": eligible_on.isoformat() if eligible_on else None,
            "grace_days_remaining": max(0, (eligible_on - today).days) if eligible_on else None,
            "can_restrict": bool(school.is_active and eligible_on and today >= eligible_on),
            "decision_at": decision.created_at.isoformat() if decision else None,
            "trial": trial}


def workspace_commercial_status(school, today):
    """Service status for school staff, without amounts or private contract details."""
    status = commercial_status(school, today)
    trial = status["trial"]
    if status["restricted"]:
        mode = "read_only"
    elif not status["billing_started"]:
        mode = "trial" if trial and trial["status"] == "active" else "free"
    elif status["oldest_overdue_on"]:
        mode = "overdue"
    elif status["schedule_review"]:
        mode = "review"
    elif status["payment_due_today"]:
        mode = "due_today"
    else:
        mode = {"active": "active", "scheduled": "scheduled", "expired": "expired"}.get(status["lifecycle"], "review")
    return {"mode": mode, "service_ends_before": status["service_ends_before"],
            "next_payment_due": status["next_payment_due"], "oldest_overdue_on": status["oldest_overdue_on"],
            "grace_days_remaining": status["grace_days_remaining"],
            "restriction_eligible_on": status["restriction_eligible_on"],
            "trial_ends_before": trial["ends_before"] if mode == "trial" else None,
            "last_service_ended_on": status["last_service_ended_on"] if status["billing_started"] else None}


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def commercial_access(request, school_id, *, school_scope=False):
    if school_scope:
        from .subscription_views import can_consult_commercial
        school = school_access(request.user, school_id)
        if school is None or not can_consult_commercial(request.user, school):
            return denied()
        if request.method != "GET":
            return JsonResponse({"error": "Consultation uniquement."}, status=405)
    else:
        if not platform_only(request):
            return denied()
        school = School.objects.filter(pk=school_id).first()
        if school is None:
            return JsonResponse({"error": "Établissement introuvable."}, status=404)
    if request.method == "GET":
        return JsonResponse(commercial_status(school, timezone.localdate()))
    data, error = parse_body(request)
    if error is not None:
        return error
    if (not isinstance(data, dict) or set(data) != {"restricted", "revision", "reason"} or
        type(data["restricted"]) is not bool or type(data["revision"]) is not int or
        not isinstance(data["reason"], str) or not 1 <= len(data["reason"].strip()) <= 240):
        return JsonResponse({"error": "Décision, révision et motif requis."}, status=422)
    with transaction.atomic():
        school = School.objects.select_for_update().get(pk=school_id)
        status = commercial_status(school, timezone.localdate())
        if data["revision"] != status["revision"]:
            return JsonResponse({"error": "Décision modifiée. Actualisez."}, status=409)
        if data["restricted"] == status["restricted"]:
            return JsonResponse({"error": "État déjà appliqué."}, status=409)
        if data["restricted"] and not status["can_restrict"]:
            return JsonResponse({"error": "Restriction non éligible : délai de grâce de 30 jours non écoulé."}, status=409)
        decision = PlatformCommercialAccessDecision.objects.create(
            school=school, revision=status["revision"]+1, restricted=data["restricted"],
            reason=data["reason"].strip(), actor=request.user)
        audit(request, "subscription_access_restricted" if decision.restricted else "subscription_access_restored",
              decision.pk, school=school, reason=decision.reason)
        return JsonResponse(commercial_status(school, timezone.localdate()), status=201)
