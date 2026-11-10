"""Configurable YEM-only payment rehearsals.

No merchant call is made. A successful rehearsal can never be used as financial
settlement or as a gate for admission; school staff must still decide/enroll.
Only school-approved, clearly fictional family accounts can use this endpoint.
"""
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import authorized

from .academic_models import AcademicLevel, AcademicYear
from .admission_models import AdmissionEvent
from .models import OrganizationMember, School, SchoolMember
from .parent_admission_models import ParentAdmissionRequest
from .parent_payment_models import ParentPaymentAttempt, SchoolDemoPaymentConfig
from .parent_payment_views import attempt_view
from .services import has_permission
from .views import access, log_event, parse_body, refuse

LABEL = "SIMULATION YEM — aucun argent reçu"


def demo_config(school):
    return SchoolDemoPaymentConfig.objects.filter(school=school).first()


def demo_amount(school, year_id, level_id, parent_user):
    if not parent_user.is_authenticated or not parent_user.is_active:
        return None
    row = demo_config(school)
    if not row or not row.enabled or str(parent_user.pk) not in row.allowed_parent_ids:
        return None
    value = row.level_amounts_xaf.get(f"{year_id}:{level_id}")
    return value if type(value) is int and 100 <= value <= 10000000 else None


def config_view(row):
    users = get_user_model().objects.filter(
        pk__in=row.allowed_parent_ids,
    ).order_by("username") if row else []
    return {
        "enabled": row.enabled if row else False,
        "revision": row.revision if row else 0,
        "level_amounts_xaf": row.level_amounts_xaf if row else {},
        "allowed_usernames": [u.username for u in users],
        "notice": LABEL,
    }


def bad(message, status=422):
    return JsonResponse({"error": message}, status=status)


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def school_demo_configuration(request, school_id):
    school, failure = access(request, school_id)
    if failure is not None:
        return failure
    if not (has_permission(request.user, school, "school.finance.manage")
            and has_permission(request.user, school, "school.admissions.manage")):
        return refuse()
    if request.method == "GET":
        return JsonResponse(config_view(demo_config(school)))
    data, failure = parse_body(request)
    if failure is not None:
        return failure
    if set(data) != {"revision", "enabled", "level_amounts_xaf", "allowed_usernames"}:
        return bad("Paramètres de simulation incomplets.")
    if type(data["revision"]) is not int or data["revision"] < 0 or type(data["enabled"]) is not bool:
        return bad("Révision ou état invalide.")
    amounts, names = data["level_amounts_xaf"], data["allowed_usernames"]
    if not isinstance(amounts, dict) or len(amounts) > 150:
        return bad("Barèmes simulés invalides.")
    if not isinstance(names, list) or len(names) > 50 or len(names) != len(set(names)) or any(
        not isinstance(name, str) or not name.startswith("yemtest-") or len(name) > 150
        for name in names
    ):
        return bad("Utilisez uniquement des comptes pilotes YEM clairement identifiés.")
    users = list(get_user_model().objects.filter(username__in=names, is_active=True))
    if len(users) != len(names) or any(
        not user.email.lower().endswith("@example.test") or user.is_staff or user.is_superuser
        or OrganizationMember.objects.filter(user=user).exists()
        or SchoolMember.objects.filter(user=user, active=True).exclude(role__code="parent").exists()
        for user in users
    ):
        return bad("Un des comptes n'est pas un parent fictif autorisé.")
    for key, amount in amounts.items():
        parts = key.split(":") if isinstance(key, str) else []
        try:
            year_id, level_id = [uuid.UUID(part) for part in parts]
        except (TypeError, ValueError):
            return bad("Année ou niveau du tarif de simulation invalide.")
        if len(parts) != 2 or type(amount) is not int or not 100 <= amount <= 10000000:
            return bad("Montant fictif invalide : entre 100 et 10 000 000 FCFA.")
        if not AcademicYear.objects.filter(school=school, pk=year_id).exists() or not AcademicLevel.objects.filter(school=school, pk=level_id).exists():
            return bad("Le tarif de simulation doit appartenir à cet établissement.")
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            row = SchoolDemoPaymentConfig.objects.select_for_update().filter(school=school).first()
            if (row.revision if row else 0) != data["revision"]:
                return bad("Paramètres modifiés : rechargez la fiche.", 409)
            row = row or SchoolDemoPaymentConfig(school=school)
            row.enabled = data["enabled"]
            row.level_amounts_xaf = amounts
            row.allowed_parent_ids = sorted(str(u.pk) for u in users)
            row.revision = row.revision + 1 if row.pk and row._state.adding is False else 1
            row.full_clean()
            row.save()
            log_event(school, request, "demo_payment_policy_updated", str(school.pk),
                      {"enabled": row.enabled, "parent_count": len(users), "level_count": len(amounts)})
    except ValidationError as exc:
        return bad(str(exc)[:300])
    return JsonResponse(config_view(row))


@never_cache
@require_POST
@authorized
def simulate_parent_payment(request, application_id):
    data, failure = parse_body(request)
    if failure is not None:
        return failure
    if data != {}:
        return bad("Aucun numéro Mobile Money ni donnée bancaire n'est requis pour une simulation.")
    with transaction.atomic():
        link = ParentAdmissionRequest.objects.select_for_update().select_related(
            "application__school", "application__year", "application__classroom__level"
        ).filter(pk=application_id, owner=request.user).first()
        if link is None:
            return bad("Candidature introuvable.", 404)
        if link.payment_choice != "demo" or not link.fee_amount_xaf:
            return bad("Cette candidature n'est pas en mode de démonstration.", 409)
        prior = ParentPaymentAttempt.objects.filter(request=link).order_by("-created_at").first()
        if prior:
            if prior.provider == "yem_demo" and prior.state == "success":
                return JsonResponse(attempt_view(prior), status=200)
            return bad("Une opération existe déjà : contactez l'établissement.", 409)
        if link.application.status not in ("submitted", "review", "accepted"):
            return bad("Une inscription terminée ou refusée ne peut plus être payée.", 409)
        if demo_amount(
            link.application.school, link.application.year_id,
            link.application.classroom.level_id, request.user,
        ) is None:
            return bad("Simulation désactivée ou compte non autorisé.", 403)
        now = timezone.now()
        attempt = ParentPaymentAttempt(
            request=link, school=link.application.school, payer=request.user,
            amount_xaf=link.fee_amount_xaf, currency="XAF", provider="yem_demo",
            provider_mode="sandbox", channel="demo", payer_phone="NON-REEL",
            merchant_reference="YEM-DEMO-" + uuid.uuid4().hex,
            transaction_id="DEMO-" + uuid.uuid4().hex,
            state="success", provider_reference="DEMO AUCUN MOUVEMENT DE FONDS",
            last_checked_at=now, finalized_at=now,
        )
        attempt.full_clean()
        attempt.save()
        AdmissionEvent.objects.create(
            school=link.application.school, application=link.application,
            previous_status=link.application.status, new_status=link.application.status,
            reason="Simulation du paiement d'admission — aucun argent reçu.",
            actor=request.user,
        )
        log_event(link.application.school, request, "demo_admission_payment", str(attempt.pk),
                  {"amount_xaf": attempt.amount_xaf, "real_money_received": False})
    return JsonResponse(attempt_view(attempt), status=201)
