"""Read-only aggregated views feeding the YEM screens (docs/maquettes).

Each endpoint is school-scoped, permission-checked and returns only what the
caller may already read through the detailed APIs; nothing here writes data.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.views import authorized
from .views import access, refuse
from .services import has_permission
from .academic_models import AcademicYear, AcademicClass
from .student_models import Student, StudentGuardian, Enrollment
from .finance_models import FeeCharge, FeePayment
from .finance_views import uid, CURRENCY_PATTERN

ZERO = Decimal("0.00")


def money(value):
    return str((value or ZERO).quantize(Decimal("0.01")))


def gate(request, school_id, permission):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, permission):
        return None, refuse()
    return school, None


def current_year(school, requested=None):
    years = AcademicYear.objects.filter(school=school)
    if requested:
        return years.filter(pk=uid(requested)).first() if uid(requested) else None
    today = timezone.localdate()
    return (years.filter(active=True, start_date__lte=today, end_date__gte=today).order_by("-start_date").first()
            or years.filter(active=True).order_by("-start_date").first()
            or years.order_by("-start_date").first())


def primary_guardians(school, student_ids):
    result = {}
    rows = StudentGuardian.objects.filter(school=school, student_id__in=student_ids, active=True).order_by("-is_primary", "full_name")
    for g in rows:
        result.setdefault(g.student_id, g)
    return result


def enrollment_balances(school, enrollment_ids, requested_currency=None):
    """Balances in the explicitly selected currency; other currencies stay selectable."""
    charges = list(FeeCharge.objects.filter(school=school, enrollment_id__in=enrollment_ids).values("id", "enrollment_id", "amount", "currency", "due_date"))
    currencies = sorted({c["currency"] for c in charges})
    currency = requested_currency or (currencies[0] if currencies else "XAF")
    paid_by_charge = dict(
        FeePayment.objects.filter(school=school, charge_id__in=[c["id"] for c in charges], void__isnull=True)
        .values_list("charge_id").annotate(total=Sum("amount")).values_list("charge_id", "total")
    )
    balances = defaultdict(lambda: {"billed": ZERO, "paid": ZERO, "overdue": ZERO, "next_due": None, "first_overdue": None})
    today = timezone.localdate()
    for c in charges:
        if c["currency"] != currency:
            continue
        b = balances[c["enrollment_id"]]
        paid = paid_by_charge.get(c["id"]) or ZERO
        remaining = c["amount"] - paid
        b["billed"] += c["amount"]
        b["paid"] += paid
        if remaining > 0 and c["due_date"]:
            if c["due_date"] < today:
                b["overdue"] += remaining
                b["first_overdue"] = min(filter(None, [b["first_overdue"], c["due_date"]]))
            elif b["next_due"] is None or c["due_date"] < b["next_due"][0]:
                b["next_due"] = (c["due_date"], remaining)
    return currency, balances


def finance_status(b):
    if not b or b["billed"] == 0:
        return "sans_frais"
    remaining = b["billed"] - b["paid"]
    if remaining <= 0:
        return "a_jour"
    return "partiel" if b["paid"] > 0 else "impaye"


@require_GET
@authorized
def students_overview(request, school_id):
    school, error = gate(request, school_id, "school.students.read")
    if error is not None:
        return error
    year = current_year(school, request.GET.get("year") or None)
    if request.GET.get("year") and year is None:
        return JsonResponse({"error": "Année scolaire introuvable."}, status=422)
    if request.GET.get("currency") and not CURRENCY_PATTERN.fullmatch(request.GET["currency"]):
        return JsonResponse({"error": "Devise ISO invalide."}, status=422)
    students = list(Student.objects.filter(school=school).order_by("last_name", "first_name")[:1000])
    ids = [s.pk for s in students]
    enrollments = {}
    if year:
        for e in Enrollment.objects.select_related("classroom").filter(school=school, year=year, student_id__in=ids, active=True):
            enrollments[e.student_id] = e
    guardians = primary_guardians(school, ids)
    finance_visible = has_permission(request.user, school, "school.finance.read")
    currency, balances = enrollment_balances(school, [e.pk for e in enrollments.values()], request.GET.get("currency")) if finance_visible else (None, {})
    today = timezone.localdate()
    rows = []
    for s in students:
        e = enrollments.get(s.pk)
        g = guardians.get(s.pk)
        b = balances.get(e.pk) if e else None
        rows.append({
            "id": str(s.pk), "student_code": s.student_code, "first_name": s.first_name, "last_name": s.last_name,
            "active": s.active,
            "enrollment": {"id": str(e.pk), "status": e.status, "enrolled_on": e.enrolled_on.isoformat(),
                           "classroom": {"id": str(e.classroom_id), "name": e.classroom.name}} if e else None,
            "guardian": {"full_name": g.full_name, "relationship": g.relationship, "phone": g.phone, "email": g.email} if g else None,
            "finance": ({"billed": money(b["billed"] if b else ZERO), "paid": money(b["paid"] if b else ZERO),
                         "balance": money((b["billed"] - b["paid"]) if b else ZERO), "status": finance_status(b)}
                        if finance_visible and e else None),
        })
    active = [r for r in rows if r["active"]]

    def enrolled_between(start, end):
        return sum(1 for e in enrollments.values() if start <= e.enrolled_on < end)

    classes = AcademicClass.objects.filter(school=school, year=year).order_by("name") if year else []
    return JsonResponse({
        "years": [{"id": str(y.pk), "name": y.name} for y in AcademicYear.objects.filter(school=school).order_by("-start_date")],
        "year": {"id": str(year.pk), "name": year.name} if year else None,
        "classes": [{"id": str(c.pk), "name": c.name} for c in classes],
        "currencies": sorted(set(FeeCharge.objects.filter(school=school, enrollment_id__in=[e.pk for e in enrollments.values()]).values_list("currency", flat=True))),
        "currency": currency,
        "finance_visible": finance_visible,
        "students": rows,
        "metrics": {
            "active": len(active),
            "enrolled": sum(1 for r in active if r["enrollment"]),
            "new_30d": enrolled_between(today - timedelta(days=30), today + timedelta(days=1)),
            "new_prev_30d": enrolled_between(today - timedelta(days=60), today - timedelta(days=30)),
            "incomplete": sum(1 for r in active if not r["guardian"] or not r["enrollment"]),
            "missing_phone": sum(1 for r in active if r["guardian"] and not r["guardian"]["phone"]),
        },
    })


def month_start(day, back=0):
    y, m = day.year, day.month - back
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return date(y, m, 1)


@require_GET
@authorized
def finance_overview(request, school_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    today = timezone.localdate()
    year = current_year(school, request.GET.get("year") or None)
    if request.GET.get("year") and year is None:
        return JsonResponse({"error": "Année scolaire introuvable."}, status=422)
    if request.GET.get("currency") and not CURRENCY_PATTERN.fullmatch(request.GET["currency"]):
        return JsonResponse({"error": "Devise ISO invalide."}, status=422)
    enrollments = {e.pk: e for e in Enrollment.objects.select_related("student", "classroom").filter(school=school, **({"year": year} if year else {}))}
    currency, balances = enrollment_balances(school, list(enrollments), request.GET.get("currency"))
    payments = FeePayment.objects.filter(school=school, void__isnull=True, charge__enrollment__year=year)
    if currency:
        payments = payments.filter(currency=currency)

    def total(qs):
        return qs.aggregate(t=Sum("amount"))["t"] or ZERO

    def by_method(qs):
        return {m: money(t) for m, t in qs.values_list("method").annotate(t=Sum("amount")).values_list("method", "t")}

    month0 = month_start(today)
    months = []
    for back in range(5, -1, -1):
        start = month_start(today, back)
        end = month_start(today, back - 1)
        months.append({"month": start.isoformat()[:7], "total": money(total(payments.filter(paid_on__gte=start, paid_on__lt=end)))})
    todays = list(payments.filter(paid_on=today).select_related("charge__enrollment__student", "charge__enrollment__classroom").order_by("-created_at")[:50])
    guardians = primary_guardians(school, [e.student_id for e in enrollments.values()])
    last_payment = {}
    for p in payments.order_by("paid_on").values("charge__enrollment_id", "paid_on"):
        last_payment[p["charge__enrollment_id"]] = p["paid_on"]
    arrears = []
    for eid, b in balances.items():
        if b["overdue"] <= 0:
            continue
        e = enrollments.get(eid)
        if e is None:
            continue
        g = guardians.get(e.student_id)
        arrears.append({
            "enrollment": str(eid), "student": f"{e.student.last_name} {e.student.first_name}", "classroom": e.classroom.name,
            "guardian": g.full_name if g else "", "phone": g.phone if g else "",
            "due_date": b["first_overdue"].isoformat() if b["first_overdue"] else None,
            "amount_due": money(b["overdue"]),
            "last_payment": last_payment[eid].isoformat() if eid in last_payment else None,
        })
    arrears.sort(key=lambda a: Decimal(a["amount_due"]), reverse=True)
    by_class = Counter(a["classroom"] for a in arrears)
    outstanding = sum((b["billed"] - b["paid"] for b in balances.values()), ZERO)
    return JsonResponse({
        "currencies": sorted(set(FeeCharge.objects.filter(school=school, enrollment__year=year).values_list("currency", flat=True))),
        "currency": currency or "XAF",
        "years": [{"id": str(y.pk), "name": y.name} for y in AcademicYear.objects.filter(school=school).order_by("-start_date")],
        "year": {"id": str(year.pk), "name": year.name} if year else None,
        "today": {
            "date": today.isoformat(), "total": money(total(payments.filter(paid_on=today))),
            "count": payments.filter(paid_on=today).count(), "by_method": by_method(payments.filter(paid_on=today)),
            "payments": [{
                "id": str(p.pk), "currency": p.currency, "amount": money(p.amount), "method": p.method, "recorded_at": p.created_at.isoformat(),
                "student": f"{p.charge.enrollment.student.last_name} {p.charge.enrollment.student.first_name}",
                "classroom": p.charge.enrollment.classroom.name, "label": p.charge.label,
            } for p in todays],
        },
        "yesterday": {"total": money(total(payments.filter(paid_on=today - timedelta(days=1)))), "count": payments.filter(paid_on=today - timedelta(days=1)).count()},
        "month": {"total": money(total(payments.filter(paid_on__gte=month0))), "previous": money(total(payments.filter(paid_on__gte=month_start(today, 1), paid_on__lt=month0))),
                  "by_method": by_method(payments.filter(paid_on__gte=month0))},
        "monthly": months,
        "outstanding": money(outstanding),
        "overdue_total": money(sum((Decimal(a["amount_due"]) for a in arrears), ZERO)),
        "families_late": len(arrears),
        "arrears": arrears[:100],
        "arrears_by_class": [{"classroom": c, "families": n} for c, n in by_class.most_common(8)],
        "active_students": Student.objects.filter(school=school, active=True).count(),
    })
