"""YEM commercial console: explicit annual contracts and manual reconciliation."""
from django.db import transaction
from django.db.models import Count, F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .academic_models import AcademicYear
from .models import School
from .student_models import Enrollment
from .subscription_models import PlatformSubscription, PlatformSubscriptionPayment
from .platform_admin_views import audit, denied
from .services import platform_only
from .school_profiles import CYCLE_LABELS
from .views import parse_body

# Suggested starting prices only. Every annual contract requires explicit rates.
DEFAULT_RATES = {"prescolaire": 1000, "primaire": 1500, "college": 2000,
                 "lycee_general": 2000, "lycee_technique": 2000}
METHODS = {"especes", "mobile_money", "virement", "autre"}


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def current_counts(school, year):
    rows = Enrollment.objects.filter(school=school, year=year, active=True, student__active=True)
    if rows.exclude(student__school=school, classroom__school=school, classroom__year=year,
                    classroom__level__school=school, classroom__level__cycle__school=school).exists():
        raise ValueError("Incohérence d'inscription : corrigez la structure avant facturation.")
    counts = {code: 0 for code in (school.education_cycles or [])}
    for row in rows.values("classroom__level__cycle__code").annotate(number=Count("student_id", distinct=True)):
        counts[row["classroom__level__cycle__code"]] = row["number"]
    return counts


def quote_lines(counts, rates):
    if not isinstance(rates, dict) or set(rates) != set(counts):
        raise ValueError("Indiquez un tarif pour chaque cycle.")
    if any(type(value) is not int or not 0 <= value <= 10000000 for value in rates.values()):
        raise ValueError("Les tarifs doivent être des francs CFA entiers positifs ou nuls.")
    return [{"cycle": code, "label": CYCLE_LABELS.get(code, code), "students": count,
             "rate_xaf": rates[code], "amount_xaf": count * rates[code]}
            for code, count in sorted(counts.items())]


def representation(row):
    payments = list(row.payments.order_by("recorded_at", "pk"))
    paid = sum(p.amount_xaf for p in payments if p.voided_at is None)
    return {"id": row.pk, "lines": row.lines, "total_xaf": row.total_xaf, "paid_xaf": paid,
            "balance_xaf": row.total_xaf - paid, "issued_at": row.issued_at.isoformat(),
            "payments": [{"id": p.pk, "reference": p.reference, "amount_xaf": p.amount_xaf,
                          "method": p.method, "recorded_at": p.recorded_at.isoformat(),
                          "voided": p.voided_at is not None, "void_reason": p.void_reason} for p in payments]}


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def subscriptions(request, school_id):
    if not platform_only(request):
        return denied()
    school = School.objects.filter(pk=school_id).first()
    if school is None:
        return fail("Établissement introuvable.", 404)
    if request.method == "GET":
        years = list(AcademicYear.objects.filter(school=school).order_by("-start_date"))
        return JsonResponse({"years": [
            {"id": str(y.pk), "name": y.name, "status": y.status, "active": y.active}
            for y in years], "suggested_year": next((str(y.pk) for y in years if y.status == "current"), None)})
    data, error = parse_body(request)
    if error is not None:
        return error
    action = data.get("action")
    fields = {"quote": {"year_id", "action"},
              "issue": {"year_id", "action", "rates", "expected_counts", "reason"},
              "payment": {"year_id", "action", "reference", "amount_xaf", "method", "reason"},
              "void": {"year_id", "action", "payment_id", "reason"}}
    if not isinstance(action, str) or action not in fields or set(data) != fields[action]:
        return fail("Action ou paramètres invalides.")
    from uuid import UUID
    try:
        year_id = UUID(data["year_id"])
    except (TypeError, ValueError, AttributeError):
        return fail("Année invalide.")
    with transaction.atomic():
        # Same school-first order as other financial/concurrent operations.
        school = School.objects.select_for_update().get(pk=school_id)
        year = AcademicYear.objects.filter(pk=year_id, school=school).first()
        if year is None:
            return fail("Année introuvable pour cet établissement.", 404)
        row = PlatformSubscription.objects.filter(year=year).first()
        if action == "quote":
            if row:
                return JsonResponse({"subscription": representation(row)})
            try:
                counts = current_counts(school, year)
            except ValueError as exc:
                return fail(str(exc), 409)
            return JsonResponse({"counts": counts, "rates": {k: DEFAULT_RATES.get(k) for k in counts},
                                 "labels": {k: CYCLE_LABELS.get(k, k) for k in counts},
                                 "can_issue": school.is_active and year.active and year.status != "closed"})
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 240:
            return fail("Motif obligatoire (240 caractères maximum).")
        reason = reason.strip()
        if action == "issue":
            if row:
                return fail("Un abonnement existe déjà pour cette année.", 409)
            if not school.is_active or not year.active or year.status == "closed":
                return fail("Établissement ou année non ouverte.", 409)
            try:
                counts = current_counts(school, year)
                expected = data["expected_counts"]
                if not isinstance(expected, dict) or any(type(v) is not int for v in expected.values()) or counts != expected:
                    return fail("Les effectifs ont changé. Rechargez le devis.", 409)
                if not counts:
                    return fail("Configurez au moins un cycle avant de créer un abonnement.", 409)
                lines = quote_lines(counts, data["rates"])
            except ValueError as exc:
                return fail(str(exc))
            row = PlatformSubscription.objects.create(year=year, lines=lines,
                total_xaf=sum(line["amount_xaf"] for line in lines), issued_by=request.user)
            audit(request, "subscription_issued", row.pk, school=school, reason=reason)
            return JsonResponse({"subscription": representation(row)}, status=201)
        if not row:
            return fail("Aucun abonnement pour cette année.", 404)
        if action == "payment":
            reference, amount, method = data["reference"], data["amount_xaf"], data["method"]
            if (not isinstance(reference, str) or not 1 <= len(reference.strip()) <= 100
                    or type(amount) is not int or amount <= 0 or not isinstance(method, str) or method not in METHODS):
                return fail("Référence, montant ou moyen de règlement invalide.")
            reference = reference.strip().upper()
            existing = row.payments.filter(reference=reference).first()
            if existing:
                if existing.amount_xaf != amount or existing.method != method or existing.voided_at:
                    return fail("Référence déjà utilisée.", 409)
                return JsonResponse({"subscription": representation(row)})
            if amount > representation(row)["balance_xaf"]:
                return fail("Le montant dépasse le solde de l'abonnement.", 409)
            payment = row.payments.create(reference=reference, amount_xaf=amount,
                                          method=method, recorded_by=request.user)
            audit(request, "subscription_payment_recorded", payment.pk, school=school, reason=reason)
            return JsonResponse({"subscription": representation(row)}, status=201)
        payment_id = data["payment_id"]
        if type(payment_id) is not int or not 1 <= payment_id <= 2**63-1:
            return fail("Identifiant de règlement invalide.")
        payment = row.payments.filter(pk=payment_id).first()
        if not payment:
            return fail("Règlement introuvable.", 404)
        if payment.voided_at is not None:
            return fail("Règlement déjà annulé.", 409)
        payment.voided_at = timezone.now()
        payment.void_reason = reason
        payment.save(update_fields=["voided_at", "void_reason"])
        audit(request, "subscription_payment_voided", payment.pk, school=school, reason=reason)
        return JsonResponse({"subscription": representation(row)})
