"""Private BWETEK commercial reporting, separate from school tuition and accounting."""
from datetime import date
from django.db.models import F, OuterRef, Subquery
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from accounts.views import authorized
from .models import School
from .services import platform_only
from .platform_admin_views import denied
from .subscription_models import PlatformSubscription, PlatformSubscriptionTrial, PlatformCommercialAccessDecision
from .subscription_amendments import effective_ledger
from .subscription_pricing import add_months, schedule_balances

PAGE_SIZE = 50
AMOUNTS = ("contracted_xaf", "amendments_xaf", "paid_xaf", "balance_xaf",
           "overdue_xaf", "due_today_xaf", "future_xaf", "unscheduled_xaf", "overpaid_xaf")
METHODS = ("especes", "mobile_money", "virement", "autre")


def zero_amounts():
    return dict.fromkeys(AMOUNTS, 0)


def commercial_report(today, year):
    schools = {}
    latest = PlatformCommercialAccessDecision.objects.filter(school_id=OuterRef("pk")).order_by("-revision")
    for school in School.objects.annotate(read_only=Subquery(latest.values("restricted")[:1])).values("id", "name", "is_active", "read_only"):
        schools[school["id"]] = {**zero_amounts(), "school_id": str(school["id"]), "school": school["name"],
            "enabled": school["is_active"], "read_only": bool(school["read_only"]), "contracts": 0,
            "active_contracts": 0, "trial": None, "review_count": 0, "late_30_xaf": 0}
    months = [{"month": f"{year}-{m:02d}", "received_xaf": 0, "voided_xaf": 0} for m in range(1, 13)]
    methods = dict.fromkeys(METHODS, 0)
    for row in PlatformSubscription.objects.select_related("year").prefetch_related("payments","amendments").iterator(chunk_size=200):
        school = schools[row.year.school_id]
        school["contracts"] += 1
        amendments = list(row.amendments.all())
        total = row.total_xaf + sum(a.amount_xaf for a in amendments)
        paid = 0
        for payment in row.payments.all():
            recorded = timezone.localtime(payment.recorded_at).date()
            if payment.voided_at is None:
                paid += payment.amount_xaf
                if recorded.year == year:
                    months[recorded.month-1]["received_xaf"] += payment.amount_xaf
                    method = payment.method if payment.method in METHODS else "autre"
                    methods[method] += payment.amount_xaf
            elif recorded.year == year:
                months[recorded.month-1]["voided_xaf"] += payment.amount_xaf
        school["contracted_xaf"] += total
        school["amendments_xaf"] += total - row.total_xaf
        school["paid_xaf"] += paid
        balance = max(0, total-paid)
        school["balance_xaf"] += balance
        school["overpaid_xaf"] += max(0, paid-total)
        # Legacy or inconsistent terms never turn into invented due dates.
        # The normalization itself may fail on malformed historical JSON.
        try:
            _, terms = effective_ledger(row, amendments)
            schedule = terms.get("schedule", [])
            valid = bool(schedule) and sum(s["amount_xaf"] for s in schedule) == total and all(
                type(s["amount_xaf"]) is int and s["amount_xaf"] >= 0 for s in schedule)
            identities = [(s["kind"], s["number"]) for s in schedule]
            if any(kind not in ("abonnement", "mise_en_service", "avenant") or
                   type(number) is not int or number < 0 for kind, number in identities):
                raise ValueError("Invalid schedule identity")
            initial = [s for s in schedule if s["kind"] == "abonnement"]
            if not initial or not valid or len(set(identities)) != len(identities):
                raise ValueError("Invalid schedule")
            start = date.fromisoformat(initial[0]["due_date"])
            end = add_months(start, 12)
            balances = schedule_balances(terms, paid, today)
        except (KeyError, TypeError, ValueError, OverflowError):
            school["review_count"] += 1
            school["unscheduled_xaf"] += balance
            continue
        if start <= today < end:
            school["active_contracts"] += 1
        for item in balances:
            key = {"overdue":"overdue_xaf","due":"due_today_xaf","upcoming":"future_xaf"}.get(item["status"])
            if key:
                school[key] += item["balance_xaf"]
            if item["days_overdue"] >= 30:
                school["late_30_xaf"] += item["balance_xaf"]
    for trial in PlatformSubscriptionTrial.objects.filter(year__school_id=F("school_id")).values("school_id","starts_on","ends_before"):
        row = schools[trial["school_id"]]
        row["trial"] = "converted" if row["contracts"] else "scheduled" if today < trial["starts_on"] else "active" if today < trial["ends_before"] else "expired"
    rows = sorted(schools.values(), key=lambda s: (-s["overdue_xaf"], -s["balance_xaf"], s["school"].casefold(), s["school_id"]))
    totals = {key: sum(s[key] for s in rows) for key in AMOUNTS}
    totals.update({"schools":len(rows), "contracted_schools":sum(s["contracts"]>0 for s in rows),
        "active_schools":sum(s["enabled"] and s["active_contracts"]>0 for s in rows),
        "read_only_schools":sum(s["read_only"] for s in rows),
        "active_trials":sum(s["enabled"] and s["trial"]=="active" for s in rows),
        "overdue_schools":sum(s["overdue_xaf"]>0 for s in rows),
        "review_count":sum(s["review_count"] for s in rows)})
    return totals, rows, months, methods


@never_cache
@require_GET
@authorized
def financial_dashboard(request):
    if not platform_only(request):
        return denied()
    today = timezone.localdate()
    year = request.GET.get("year", str(today.year))
    page = request.GET.get("page", "1")
    status = request.GET.get("status", "all")
    search = request.GET.get("q", "").strip()
    if (not year.isascii() or not year.isdecimal() or len(year)!=4 or not 2000 <= int(year) <= today.year
        or not page.isascii() or not page.isdecimal() or len(page)>7 or int(page)<1
        or len(search)>120 or status not in ("all","overdue","read_only","trial","no_contract","review")):
        return JsonResponse({"error":"Filtres financiers invalides."},status=422)
    year, page = int(year), int(page)
    totals, rows, months, methods = commercial_report(today, year)
    filters = {"all":lambda s:True, "overdue":lambda s:s["overdue_xaf"]>0,
        "read_only":lambda s:s["read_only"], "trial":lambda s:s["trial"]=="active",
        "no_contract":lambda s:not s["contracts"], "review":lambda s:s["review_count"]>0}
    rows = [s for s in rows if filters[status](s) and search.casefold() in s["school"].casefold()]
    pages = max(1,(len(rows)+PAGE_SIZE-1)//PAGE_SIZE)
    page=min(page,pages)
    return JsonResponse({"as_of":today.isoformat(),"year":year,"totals":totals,"months":months,
        "year_received_xaf":sum(m["received_xaf"] for m in months),"year_voided_xaf":sum(m["voided_xaf"] for m in months),
        "methods":methods,"count":len(rows),"page":page,"pages":pages,"schools":rows[(page-1)*PAGE_SIZE:page*PAGE_SIZE]})
