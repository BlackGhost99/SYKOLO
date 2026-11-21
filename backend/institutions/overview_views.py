"""Read-only aggregated views feeding the YEM screens (docs/maquettes).

Each endpoint is school-scoped, permission-checked and returns only what the
caller may already read through the detailed APIs; nothing here writes data.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import CharField, Q, Sum, Value
from django.db.models.functions import Cast, Replace
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.views import authorized
from .views import access, refuse
from .services import has_permission
from .student_access import can_read_profile, can_read_sensitive, can_read_finance
from .academic_models import AcademicYear, AcademicClass
from .student_models import Student, StudentGuardian, Enrollment
from .finance_models import FeeCharge, FeePayment
from .finance_views import uid, CURRENCY_PATTERN
from .finance_evidence import classify_payment, evidence_totals

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
    return (years.filter(status=AcademicYear.STATUS_CURRENT).first()
            or years.filter(active=True, start_date__lte=today, end_date__gte=today).order_by("-start_date").first()
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
    charges = list(FeeCharge.objects.filter(school=school, enrollment_id__in=enrollment_ids).values(
        "id", "enrollment_id", "amount", "scholarship_discount", "currency", "due_date", "label",
    ))
    currencies = sorted({c["currency"] for c in charges})
    currency = requested_currency or (currencies[0] if currencies else "XAF")
    paid_by_charge = dict(
        FeePayment.objects.filter(school=school, charge_id__in=[c["id"] for c in charges], void__isnull=True)
        .values_list("charge_id").annotate(total=Sum("amount")).values_list("charge_id", "total")
    )
    from .historical_finance import historical_credits
    opening = historical_credits(school.pk, [c["id"] for c in charges])
    for key, amount in opening.items():
        paid_by_charge[key] = paid_by_charge.get(key, ZERO) + amount
    balances = defaultdict(lambda: {"billed": ZERO, "paid": ZERO, "overdue": ZERO, "next_due": None, "first_overdue": None, "overdue_items": [], "due_today": ZERO})
    today = timezone.localdate()
    for c in charges:
        if c["currency"] != currency:
            continue
        b = balances[c["enrollment_id"]]
        paid = paid_by_charge.get(c["id"]) or ZERO
        # A validated grant reduces the enforceable debt, never the cash received.
        # Display net tuition consistently with the student's official dossier.
        net_due = c["amount"] - c["scholarship_discount"]
        remaining = net_due - paid
        b["billed"] += net_due
        b["paid"] += paid
        if remaining > 0 and c["due_date"]:
            if c["due_date"] < today:
                b["overdue"] += remaining
                b["overdue_items"].append({"label": c["label"], "date": c["due_date"].isoformat(), "balance": money(remaining)})
                b["first_overdue"] = min(filter(None, [b["first_overdue"], c["due_date"]]))
            else:
                if c["due_date"] == today:
                    b["due_today"] += remaining
                if b["next_due"] is None or c["due_date"] < b["next_due"][0]:
                    b["next_due"] = (c["due_date"], remaining)
    return currency, balances


def finance_status(b):
    if not b or b["billed"] == 0:
        return "sans_frais"
    remaining = b["billed"] - b["paid"]
    if remaining <= 0:
        return "a_jour"
    return "partiel" if b["paid"] > 0 else "impaye"


SEARCH_PAGE_SIZE = 25


def search_page(request):
    value = request.GET.get("page", "1")
    if not value.isascii() or not value.isdigit() or len(value) > 7:
        raise ValueError("Page invalide.")
    return max(1, int(value))


def student_search_terms(request):
    return request.GET.get("q", "")[:120].split()[:10]


def payment_student_search(request, school, year):
    """Read-only, scoped lookup for the cash desk; no full financial roster."""
    if not has_permission(request.user, school, "school.finance.read"):
        return refuse()
    try:
        page = search_page(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    base = Enrollment.objects.filter(
        school=school, year=year, year__school=school, active=True,
        student__school=school, student__active=True,
        classroom__school=school, classroom__year=year,
    ).select_related("student", "classroom")
    if not year:
        base = base.none()
    rows = base
    classroom = request.GET.get("classroom")
    if classroom:
        if not uid(classroom):
            return JsonResponse({"error": "Classe invalide."}, status=422)
        rows = rows.filter(classroom_id=uid(classroom))
    for term in student_search_terms(request):
        match = (Q(student__last_name__icontains=term) |
                 Q(student__first_name__icontains=term) |
                 Q(student__student_code__icontains=term))
        if term.upper().startswith("YEM-"):
            fragment = term[4:].replace("-", "")
            if fragment and all(ch in "0123456789abcdefABCDEF" for ch in fragment):
                rows = rows.annotate(identity_hex=Replace(Cast("student__identity_id", CharField()), Value("-"), Value("")))
                match |= Q(identity_hex__istartswith=fragment)
        rows = rows.filter(match)
    total = rows.count()
    page = min(page, max(1, (total + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE))
    start = (page - 1) * SEARCH_PAGE_SIZE
    records = list(rows.order_by("student__last_name", "student__first_name", "pk")[start:start + SEARCH_PAGE_SIZE])
    selected_id = uid(request.GET.get("selected") or "")
    selected = base.filter(pk=selected_id).first() if selected_id else None
    guardians = primary_guardians(school, [e.student_id for e in records] +
                                  ([selected.student_id] if selected else [])) if can_read_sensitive(request.user, school) else {}

    def serialize(e):
        s = e.student
        g = guardians.get(s.pk)
        return {
            "id": str(s.pk), "student_code": s.student_code, "matricule_yem": s.matricule_yem,
            "last_name": s.last_name, "first_name": s.first_name, "active": s.active,
            "enrollment": {"id": str(e.pk), "classroom": {"id": str(e.classroom_id), "name": e.classroom.name}},
            "guardian": {"full_name": g.full_name, "relationship": g.relationship, "phone": g.phone} if g else None,
        }

    classes = AcademicClass.objects.filter(school=school, year=year).order_by("name") if year else []
    return JsonResponse({
        "students": [serialize(e) for e in records],
        "selected": serialize(selected) if selected else None,
        "classes": [{"id": str(cl.pk), "name": cl.name} for cl in classes],
        "page": page, "page_size": SEARCH_PAGE_SIZE, "total": total,
    }, headers={"Cache-Control": "no-store"})


def filtered_arrears(request, arrears):
    """Filter the complete set, before slicing; totals remain school-wide."""
    terms = [term.casefold() for term in student_search_terms(request)]
    classroom = request.GET.get("classroom", "")
    period = request.GET.get("period", "")
    status = request.GET.get("status", "")
    if classroom and not uid(classroom):
        raise ValueError("Classe invalide.")
    if classroom:
        classroom = str(uid(classroom))
    if period:
        try:
            if len(period) != 7 or date.fromisoformat(period + "-01").isoformat()[:7] != period:
                raise ValueError()
        except ValueError:
            raise ValueError("Période invalide.") from None
    if status not in ("", "with_payment", "without_payment"):
        raise ValueError("Statut invalide.")
    return [
        row for row in arrears
        if (not classroom or row["classroom_id"] == classroom)
        and (not period or any(item["date"][:7] == period for item in row["overdue_items"]))
        and (not status or bool(row["last_payment"]) == (status == "with_payment"))
        and all(term in " ".join(str(row.get(key) or "") for key in
                ("student", "student_code", "matricule_yem", "guardian", "phone")).casefold() for term in terms)
    ]


@require_GET
@authorized
def students_overview(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not (can_read_profile(request.user, school) or can_read_finance(request.user, school)):
        return refuse()
    sensitive_visible = can_read_sensitive(request.user, school)
    year = current_year(school, request.GET.get("year") or None)
    if request.GET.get("year") and year is None:
        return JsonResponse({"error": "Année scolaire introuvable."}, status=422)
    if request.GET.get("currency") and not CURRENCY_PATTERN.fullmatch(request.GET["currency"]):
        return JsonResponse({"error": "Devise ISO invalide."}, status=422)
    if request.GET.get("payment_search") == "1":
        return payment_student_search(request, school, year)
    student_queryset = Student.objects.filter(school=school)
    # When explicitly viewing a historical cohort, hide pupils who joined
    # only in another year. The default all-pupils directory remains unchanged.
    if request.GET.get("year") and year:
        student_queryset = student_queryset.filter(enrollments__year=year).distinct()
    students = list(student_queryset.order_by("last_name", "first_name")[:1000])
    ids = [s.pk for s in students]
    enrollments = {}
    if year:
        for e in Enrollment.objects.select_related("classroom").filter(school=school, year=year, student_id__in=ids, active=True):
            enrollments[e.student_id] = e
    guardians = primary_guardians(school, ids) if sensitive_visible else {}
    finance_visible = can_read_finance(request.user, school)
    currency, balances = enrollment_balances(school, [e.pk for e in enrollments.values()], request.GET.get("currency")) if finance_visible else (None, {})
    today = timezone.localdate()
    methods, last_paid = defaultdict(set), {}
    if finance_visible:
        cleared = FeePayment.objects.filter(
            school=school, void__isnull=True, charge__currency=currency,
            charge__enrollment_id__in=[e.pk for e in enrollments.values()],
        )
        for eid, method, paid_on in cleared.order_by("paid_on").values_list(
            "charge__enrollment_id", "method", "paid_on"
        ):
            methods[eid].add(method)
            last_paid[eid] = paid_on
    from .enrollment_form import load_config, missing_documents
    form, _ = load_config(school) if sensitive_visible else (None, None)
    rows = []
    for s in students:
        e = enrollments.get(s.pk)
        g = guardians.get(s.pk)
        b = balances.get(e.pk) if e else None
        rows.append({
            "id": str(s.pk), "student_code": s.student_code, "matricule_yem": s.matricule_yem, "first_name": s.first_name, "last_name": s.last_name,
            "active": s.active, "missing_documents": len(missing_documents(form, s.documents)) if sensitive_visible else None,
            "enrollment": {"id": str(e.pk), "status": e.status, "enrolled_on": e.enrolled_on.isoformat(),
                           "classroom": {"id": str(e.classroom_id), "name": e.classroom.name}} if e else None,
            "guardian": {"full_name": g.full_name, "relationship": g.relationship, "phone": g.phone, "email": g.email} if g else None,
            "finance": ({"billed": money(b["billed"] if b else ZERO), "paid": money(b["paid"] if b else ZERO),
                         "balance": money((b["billed"] - b["paid"]) if b else ZERO), "status": finance_status(b),
                         "overdue": money(b["overdue"] if b else ZERO), "methods": sorted(methods[e.pk]),
                         "last_payment": last_paid[e.pk].isoformat() if e.pk in last_paid else None}
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
        "sensitive_visible": sensitive_visible,
        "students": rows,
        "metrics": {
            "active": len(active),
            "enrolled": sum(1 for r in active if r["enrollment"]),
            "new_30d": enrolled_between(today - timedelta(days=30), today + timedelta(days=1)),
            "new_prev_30d": enrolled_between(today - timedelta(days=60), today - timedelta(days=30)),
            "incomplete": sum(1 for r in active if not r["guardian"] or not r["enrollment"]) if sensitive_visible else 0,
            "missing_documents": sum(1 for r in active if r["missing_documents"]) if sensitive_visible else 0,
            "missing_phone": sum(1 for r in active if r["guardian"] and not r["guardian"]["phone"]) if sensitive_visible else 0,
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
    evidence = evidence_totals(payments)

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
    guardians = (primary_guardians(school, [e.student_id for e in enrollments.values()])
                 if can_read_sensitive(request.user, school) else {})
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
            "classroom_id": str(e.classroom_id), "student_code": e.student.student_code, "matricule_yem": e.student.matricule_yem,
            "guardian": g.full_name if g else "", "phone": g.phone if g else "",
            "due_date": b["first_overdue"].isoformat() if b["first_overdue"] else None,
            "amount_due": money(b["overdue"]),
            "overdue_items": sorted(b["overdue_items"], key=lambda item: (item["date"], item["label"])),
            "due_today": money(b["due_today"]),
            "remaining": money(b["billed"] - b["paid"]),
            "last_payment": last_payment[eid].isoformat() if eid in last_payment else None,
        })
    arrears.sort(key=lambda a: (-Decimal(a["amount_due"]), a["enrollment"]))
    by_class = Counter(a["classroom"] for a in arrears)
    outstanding = sum((b["billed"] - b["paid"] for b in balances.values()), ZERO)
    arrears_meta = {}
    visible_arrears = arrears[:100]
    if request.GET.get("arrears_search") == "1":
        try:
            filtered = filtered_arrears(request, arrears)
            page = min(search_page(request), max(1, (len(filtered) + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=422)
        start = (page - 1) * SEARCH_PAGE_SIZE
        visible_arrears = filtered[start:start + SEARCH_PAGE_SIZE]
        classes = AcademicClass.objects.filter(school=school, year=year).order_by("name") if year else []
        arrears_meta = {
            "arrears_total": len(filtered), "arrears_page": page, "arrears_page_size": SEARCH_PAGE_SIZE,
            "arrears_classes": [{"id": str(cl.pk), "name": cl.name} for cl in classes],
        }
    return JsonResponse({
        "currencies": sorted(set(FeeCharge.objects.filter(school=school, enrollment__year=year).values_list("currency", flat=True))),
        "currency": currency or "XAF",
        "revenue_certified": False,
        "evidence": evidence.get(currency or "XAF", {
            "explicit_demo": "0.00",
            "legacy_cash_unverified": "0.00",
            "other_declared": "0.00",
        }),
        "note": ("Les montants affichés comme encaissés sont des écritures déclaratives, "
                 "non des recettes vérifiées. Les anciennes écritures cash et les simulations "
                 "sont identifiées séparément dans evidence."),
        "years": [{"id": str(y.pk), "name": y.name} for y in AcademicYear.objects.filter(school=school).order_by("-start_date")],
        "year": {"id": str(year.pk), "name": year.name} if year else None,
        "today": {
            "date": today.isoformat(), "total": money(total(payments.filter(paid_on=today))),
            "count": payments.filter(paid_on=today).count(), "by_method": by_method(payments.filter(paid_on=today)),
            "payments": [{
                "id": str(p.pk), "currency": p.currency, "amount": money(p.amount), "method": p.method,
                "evidence_class": classify_payment(p.method, p.charge.label),
                "recorded_at": p.created_at.isoformat(),
                "student": f"{p.charge.enrollment.student.last_name} {p.charge.enrollment.student.first_name}",
                "classroom": p.charge.enrollment.classroom.name, "label": p.charge.label,
            } for p in todays],
        },
        "yesterday": {"total": money(total(payments.filter(paid_on=today - timedelta(days=1)))), "count": payments.filter(paid_on=today - timedelta(days=1)).count()},
        "month": {"total": money(total(payments.filter(paid_on__gte=month0))), "previous": money(total(payments.filter(paid_on__gte=month_start(today, 1), paid_on__lt=month0))),
                  "by_method": by_method(payments.filter(paid_on__gte=month0))},
        "monthly": months,
        "year_by_method": by_method(payments.filter(charge__enrollment__year=year)) if year else {},
        "year_total": money(total(payments.filter(charge__enrollment__year=year))) if year else money(ZERO),
        "outstanding": money(outstanding),
        "overdue_total": money(sum((Decimal(a["amount_due"]) for a in arrears), ZERO)),
        "families_late": len(arrears),
        "arrears": visible_arrears,
        **arrears_meta,
        "arrears_by_class": [{"classroom": c, "families": n} for c, n in by_class.most_common(8)],
        "active_students": Student.objects.filter(
            school=school, active=True,
            **({"enrollments__year": year} if request.GET.get("year") and year else {}),
        ).distinct().count(),
    })
