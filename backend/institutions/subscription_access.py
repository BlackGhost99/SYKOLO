"""Commercial lifecycle and manual, narrowly scoped restrictions.

Expiry and late payments never change a school's activation or access by themselves.
"""
from datetime import date
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
    for row in contracts:
        _, terms = effective_ledger(row)
        paid = sum(p.amount_xaf for p in row.payments.all() if p.voided_at is None)
        initial = [s for s in (row.commercial_terms or {}).get("schedule", []) if s["kind"] == "abonnement"]
        if not initial:
            unknown = True
        else:
            start = date.fromisoformat(initial[0]["due_date"])
            end = add_months(start, 12)
            if start <= today < end:
                active = True
                next_end = max(next_end or end, end)
            elif today < start:
                future = True
            else:
                expired = True
        for item in schedule_balances(terms, paid, today):
            if item["days_overdue"]:
                overdue += item["balance_xaf"]
            if item["days_overdue"] >= 30:
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
    decision = last_decision(school)
    return {"lifecycle": lifecycle, "service_ends_before": next_end.isoformat() if next_end else None,
            "overdue_xaf": overdue, "late_30_xaf": late_30,
            "restricted": bool(decision and decision.restricted),
            "revision": decision.revision if decision else 0,
            "can_restrict": bool(school.is_active and (lifecycle == "expired" or late_30 > 0)),
            "decision_at": decision.created_at.isoformat() if decision else None,
            "trial": trial}


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
            return JsonResponse({"error": "Restriction non éligible : expiration ou impayé de 30 jours requis."}, status=409)
        decision = PlatformCommercialAccessDecision.objects.create(
            school=school, revision=status["revision"]+1, restricted=data["restricted"],
            reason=data["reason"].strip(), actor=request.user)
        audit(request, "subscription_access_restricted" if decision.restricted else "subscription_access_restored",
              decision.pk, school=school, reason=decision.reason)
        return JsonResponse(commercial_status(school, timezone.localdate()), status=201)
