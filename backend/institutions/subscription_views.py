"""YEM commercial console: explicit annual contracts and manual reconciliation."""
from django.db import transaction
from django.db.models import Count, F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .academic_models import AcademicYear
from .models import School, SchoolMember
from .student_models import Enrollment
from .subscription_models import PlatformSubscription, PlatformSubscriptionPayment, PlatformSubscriptionPolicy
from .platform_admin_views import audit, denied
from .services import platform_only, school_access, owns_school
from .cycle_scope import scoped_cycle_ids
from .school_profiles import CYCLE_LABELS
from .subscription_pricing import (DEFAULT_RATES, DEFAULT_MINIMUMS, PERIODS, quote_lines,
    calculate_terms, validate_schedule, setup_fee, schedule_balances)
from .views import parse_body
from .finance_document_pdf import previewable_pdf
from .subscription_document_pdf import document_links, render_commercial_document
from .subscription_amendments import (amendment_rows, amendment_quote, effective_ledger,
    serialize_amendment, start_trial, trial_summary)

METHODS = {"especes", "mobile_money", "virement", "autre"}


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def current_counts_by_year(school_years):
    """Shared batched counting rule for the school quote and commercial console."""
    counts = {year.pk: {code: 0 for code in (school.education_cycles or [])}
              for school, year in school_years}
    errors = {}
    if not counts:
        return counts, errors
    rows = Enrollment.objects.filter(year_id__in=counts, active=True, student__active=True)
    inconsistent = rows.exclude(school_id=F("year__school_id"), student__school_id=F("school_id"),
        classroom__school_id=F("school_id"), classroom__year_id=F("year_id"),
        classroom__level__school_id=F("school_id"), classroom__level__cycle__school_id=F("school_id"))
    for year_id in inconsistent.values_list("year_id", flat=True).distinct():
        errors[year_id] = "Incohérence d'inscription : corrigez la structure avant facturation."
    for row in rows.values("year_id", "classroom__level__cycle__code").annotate(number=Count("student_id", distinct=True)):
        year_id, code = row["year_id"], row["classroom__level__cycle__code"]
        if year_id in errors:
            continue
        if code not in counts[year_id]:
            errors[year_id] = "Inscriptions sur un cycle non ouvert : corrigez la classification avant facturation."
        else:
            counts[year_id][code] = row["number"]
    return counts, errors


def current_counts(school, year):
    if year.school_id != school.pk:
        raise ValueError("Année scolaire étrangère à l'établissement.")
    counts, errors = current_counts_by_year([(school, year)])
    if year.pk in errors:
        raise ValueError(errors[year.pk])
    return counts[year.pk]

def policy_snapshot(lock=False):
    query = PlatformSubscriptionPolicy.objects
    if lock:
        row, _ = query.get_or_create(pk=1, defaults={"rates": DEFAULT_RATES, "minimums": DEFAULT_MINIMUMS})
        row = query.select_for_update().get(pk=1)
    else:
        row = query.filter(pk=1).first()
    return {"rates": row.rates if row else DEFAULT_RATES,
            "minimums": row.minimums if row else DEFAULT_MINIMUMS,
            "revision": row.revision if row else 1}


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def pricing_policy(request):
    if not platform_only(request):
        return denied()
    if request.method == "GET":
        return JsonResponse(policy_snapshot())
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"rates", "minimums", "revision", "reason"}:
        return fail("Paramètres tarifaires invalides.")
    reason = data["reason"]
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 240:
        return fail("Motif obligatoire.")
    if type(data["revision"]) is not int:
        return fail("Révision invalide.")
    try:
        rates = validate_schedule(data["rates"])
        minimums = validate_schedule(data["minimums"])
        if len({rates[k] for k in ("college", "lycee_general", "lycee_technique")}) != 1 or len({minimums[k] for k in ("college", "lycee_general", "lycee_technique")}) != 1:
            raise ValueError("Collège et lycées partagent la même grille.")
        if not minimums["prescolaire"] <= minimums["primaire"] <= minimums["college"]:
            raise ValueError("Les minimums doivent suivre l'ordre des cycles.")
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        previous = policy_snapshot(lock=True)
        if previous["revision"] != data["revision"]:
            return fail("La grille a changé. Rechargez-la.", 409)
        row = PlatformSubscriptionPolicy.objects.get(pk=1)
        row.rates = rates
        row.minimums = minimums
        row.revision += 1
        row.save(update_fields=["rates", "minimums", "revision", "updated_at"])
        audit(request, "subscription_policy_updated", row.revision, reason=reason.strip())
        return JsonResponse(policy_snapshot())


def quote_for(school, year, policy, counts):
    rates = {k: policy["rates"][k] for k in counts}
    minimums = {k: policy["minimums"][k] for k in counts}
    first_due = max(year.start_date, timezone.localdate())
    terms = calculate_terms(counts, rates, minimums, first_due=first_due, revision=policy["revision"])
    prior = PlatformSubscription.objects.filter(year__school=school).exists()
    return {"counts": counts, "rates": rates, "minimums": minimums, "policy_revision": policy["revision"],
            "labels": {k: CYCLE_LABELS[k] for k in counts}, "terms": terms,
            "first_due": first_due.isoformat(), "setup_suggested_xaf": 0 if prior else setup_fee(sum(counts.values())),
            "can_issue": school.is_active and year.active and year.status != "closed" and timezone.localdate() <= year.end_date}


def representation(row):
    payments = sorted(row.payments.all(), key=lambda p: (p.recorded_at, p.pk))
    paid = sum(p.amount_xaf for p in payments if p.voided_at is None)
    amendments = amendment_rows(row)
    total, terms = effective_ledger(row, amendments)
    return {"id": row.pk, "lines": row.lines, "total_xaf": total, "paid_xaf": paid,
            "original_total_xaf": row.total_xaf, "amendments": [serialize_amendment(a) for a in amendments],
            "terms": row.commercial_terms, "schedule": schedule_balances(terms, paid, timezone.localdate()),
            "balance_xaf": total - paid, "issued_at": row.issued_at.isoformat(),
            "documents": document_links(row),
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
              "issue": {"year_id", "action", "policy_revision", "expected_counts", "reason", "period", "discount_xaf", "include_setup", "expected_total_xaf"},
              "payment": {"year_id", "action", "reference", "amount_xaf", "method", "reason"},
              "void": {"year_id", "action", "payment_id", "reason"},
              "amendment_quote": {"year_id", "action"},
              "amendment_issue": {"year_id", "action", "expected", "reason"},
              "trial_start": {"year_id", "action", "days", "reason"}}
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
        today = timezone.localdate()
        trial = trial_summary(school, today)
        if action == "quote":
            if row:
                return JsonResponse({"subscription": representation(row), "trial": trial})
            try:
                counts = current_counts(school, year)
                if not counts or not set(counts).issubset(CYCLE_LABELS):
                    raise ValueError("Configurez et vérifiez les cycles de l'établissement.")
                return JsonResponse(quote_for(school, year, policy_snapshot(), counts) | {"trial": trial, "can_trial": trial is None and not PlatformSubscription.objects.filter(year__school=school).exists()})
            except ValueError as exc:
                return fail(str(exc), 409)
        if action == "amendment_quote":
            if not row:
                return fail("Aucun abonnement pour cette année.", 404)
            if not school.is_active or not year.active or year.status == "closed":
                return fail("Établissement ou année non ouverte.", 409)
            try:
                return JsonResponse({"amendment": amendment_quote(row, current_counts(school, year), today)})
            except ValueError as exc:
                return fail(str(exc), 409)
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 240:
            return fail("Motif obligatoire (240 caractères maximum).")
        reason = reason.strip()
        if action == "trial_start":
            try:
                item = start_trial(school, year, today, data["days"], reason, request.user)
            except ValueError as exc:
                return fail(str(exc), 409)
            audit(request, "subscription_trial_started", item.pk, school=school, reason=reason)
            return JsonResponse({"trial": trial_summary(school, today)}, status=201)
        if action == "issue":
            if row:
                return fail("Un abonnement existe déjà pour cette année.", 409)
            if not school.is_active or not year.active or year.status == "closed" or timezone.localdate() > year.end_date:
                return fail("Établissement ou année non ouverte.", 409)
            try:
                counts = current_counts(school, year)
                expected = data["expected_counts"]
                if not isinstance(expected, dict) or any(type(v) is not int for v in expected.values()) or counts != expected:
                    return fail("Les effectifs ont changé. Rechargez le devis.", 409)
                if not counts:
                    return fail("Configurez au moins un cycle avant de créer un abonnement.", 409)
                policy = policy_snapshot(lock=True)
                if type(data["policy_revision"]) is not int or data["policy_revision"] != policy["revision"]:
                    return fail("La grille a changé. Rechargez le devis.", 409)
                if not set(counts).issubset(CYCLE_LABELS):
                    raise ValueError("Cycle non reconnu.")
                quote = quote_for(school, year, policy, counts)
                if type(data["include_setup"]) is not bool or not isinstance(data["period"], str):
                    raise ValueError("Modalité ou mise en service invalide.")
                if data["include_setup"] and not quote["setup_suggested_xaf"]:
                    return fail("La mise en service ne peut être facturée de nouveau.", 409)
                terms = calculate_terms(counts, quote["rates"], quote["minimums"], period=data["period"],
                    discount=data["discount_xaf"], setup=quote["setup_suggested_xaf"] if data["include_setup"] else 0,
                    first_due=max(year.start_date, timezone.localdate()), revision=policy["revision"])
                if type(data["expected_total_xaf"]) is not int or data["expected_total_xaf"] != terms["total_xaf"]:
                    return fail("Le montant a changé. Rechargez le devis.", 409)
                lines = quote_lines(counts, quote["rates"])
            except ValueError as exc:
                return fail(str(exc))
            row = PlatformSubscription.objects.create(year=year, lines=lines,
                commercial_terms=terms, total_xaf=terms["total_xaf"], issued_by=request.user)
            audit(request, "subscription_issued", row.pk, school=school, reason=reason)
            return JsonResponse({"subscription": representation(row), "trial": trial_summary(school, today)}, status=201)
        if not row:
            return fail("Aucun abonnement pour cette année.", 404)
        if action == "amendment_issue":
            if not school.is_active or not year.active or year.status == "closed":
                return fail("Établissement ou année non ouverte.", 409)
            try:
                quote = amendment_quote(row, current_counts(school, year), today)
            except ValueError as exc:
                return fail(str(exc), 409)
            # Canonical JSON comparison rejects booleans masquerading as integer values.
            import json
            if json.dumps(data["expected"], sort_keys=True) != json.dumps(quote, sort_keys=True):
                return fail("Devis d’avenant modifié. Actualisez-le.", 409)
            if not quote["additions"]:
                return fail("Aucun effectif supplémentaire à facturer.", 409)
            item = row.amendments.create(revision=quote["revision"], effective_on=today, snapshot=quote,
                                         amount_xaf=quote["amount_xaf"], reason=reason, issued_by=request.user)
            audit(request, "subscription_amendment_issued", item.pk, school=school, reason=reason)
            return JsonResponse({"subscription": representation(row)}, status=201)
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


@never_cache
@require_http_methods(["GET"])
@authorized
def owner_subscriptions(request, school_id):
    school = school_access(request.user, school_id)
    if school is None or not can_consult_commercial(request.user, school):
        return denied()
    # Only issued contracts belonging to the requested school; no private audit notes.
    records = PlatformSubscription.objects.filter(year__school=school).select_related("year").prefetch_related("payments", "amendments").order_by("-year__start_date")
    data = []
    for row in records:
        item = representation(row)
        data.append({k: item[k] for k in ("id", "lines", "total_xaf", "paid_xaf", "balance_xaf", "terms", "schedule", "issued_at", "original_total_xaf", "amendments")} |
                    {"year": row.year.name, "year_id": str(row.year_id),
                     "documents": document_links(row, school_scope=True)})
    return JsonResponse({"subscriptions": data, "trial": trial_summary(school, timezone.localdate())})


def can_consult_commercial(user, school):
    """School-wide commercial amounts are never exposed to cycle-limited staff or families."""
    if owns_school(user, school):
        return True
    if scoped_cycle_ids(user, school) is not None:
        return False
    member = SchoolMember.objects.select_related("role").filter(
        school=school, user=user, active=True, role__school=school).first()
    if not member:
        return False
    roles = {member.role.code, *member.additional_roles.filter(school=school).values_list("code", flat=True)}
    return bool(roles & {"direction", "principal", "proviseur"})


@never_cache
@require_http_methods(["GET"])
@authorized
@previewable_pdf
def commercial_document(request, school_id, subscription_id, payment_id=None, amendment_id=None, *, school_scope=False):
    """Only the platform MFA session or the authorized school management may read PDFs."""
    if school_scope:
        school = school_access(request.user, school_id)
        if school is None or not can_consult_commercial(request.user, school):
            return denied()
    elif not platform_only(request):
        return denied()
    if any(not 1 <= value <= 2**63 - 1 for value in (subscription_id, payment_id, amendment_id) if value is not None):
        return fail("Document introuvable.", 404)
    row = PlatformSubscription.objects.select_related("year__school").filter(
        pk=subscription_id, year__school_id=school_id).first()
    if row is None:
        return fail("Document introuvable.", 404)
    payment = None
    if payment_id is not None:
        payment = row.payments.filter(pk=payment_id).first()
        if payment is None:
            return fail("Document introuvable.", 404)
    amendment = None
    if amendment_id is not None:
        amendment = row.amendments.filter(pk=amendment_id).first()
        if amendment is None:
            return fail("Document introuvable.", 404)
    try:
        return render_commercial_document(row, payment, amendment=amendment)
    except (ValueError, TypeError, KeyError):
        return fail("Données contractuelles incohérentes. Contactez BWETEK.", 409)


@never_cache
@require_http_methods(["GET"])
@authorized
def subscription_simulation(request, school_id, *, school_scope=False):
    """Current enrollment-based estimate; never creates or reprices a contract."""
    from uuid import UUID
    from .school_profiles import SCHOOL_PROFILES
    if school_scope:
        school = school_access(request.user, school_id)
        if school is None or not can_consult_commercial(request.user, school):
            return denied()
    else:
        if not platform_only(request):
            return denied()
        school = School.objects.filter(pk=school_id).first()
        if school is None:
            return fail("Établissement introuvable.", 404)
    if set(request.GET) - {"year_id"}:
        return fail("Les effectifs sont calculés à partir des inscriptions réelles.")
    years = list(AcademicYear.objects.filter(school=school).order_by("-start_date"))
    selected = request.GET.get("year_id")
    if selected:
        try:
            selected = UUID(selected)
        except (ValueError, TypeError, AttributeError):
            return fail("Année invalide.")
        year = next((y for y in years if y.pk == selected), None)
        if year is None:
            return fail("Année introuvable pour cet établissement.", 404)
    else:
        year = next((y for y in years if y.status == "current"), years[0] if years else None)
    result = {"school": {"name": school.name, "type_label": SCHOOL_PROFILES.get(school.school_type, {}).get("label", "Établissement")},
              "years": [{"id": str(y.pk), "name": y.name} for y in years],
              "year_id": str(year.pk) if year else None, "simulation": None, "contracted": False}
    if year is not None:
        contract = PlatformSubscription.objects.filter(year=year).first()
        result["contracted"] = contract is not None
        result["billing_started"] = contract is not None
        result["billing_activated_on"] = timezone.localtime(contract.issued_at).date().isoformat() if contract else None
        result["first_contract_due"] = next((s["due_date"] for s in (contract.commercial_terms or {}).get("schedule", []) if s.get("kind") == "abonnement"), None) if contract else None
        try:
            counts = current_counts(school, year)
            result["actual_counts"] = counts
            policy = policy_snapshot()
            quote = quote_for(school, year, policy, counts)
            options = {}
            for period in PERIODS:
                terms = calculate_terms(counts, quote["rates"], quote["minimums"], period=period,
                    first_due=max(year.start_date, timezone.localdate()), revision=policy["revision"])
                # Prices are live estimates only. Dates belong exclusively to the signed ledger.
                terms["schedule"] = [{k: value for k, value in s.items() if k != "due_date"} for s in terms["schedule"]]
                options[period] = terms
            result["simulation"] = {"policy_revision": policy["revision"],
                "lines": quote_lines(counts, quote["rates"]),
                "setup_suggested_xaf": quote["setup_suggested_xaf"], "options": options}
        except (ValueError, KeyError) as exc:
            result["error"] = str(exc) if isinstance(exc, ValueError) else "Grille commerciale incomplète : contactez BWETEK."
    return JsonResponse(result)
