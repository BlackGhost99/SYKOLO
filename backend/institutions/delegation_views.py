"""Explicit per-school grants; job titles never participate in authorization."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .models import School, SchoolMember, PermissionDelegation
from .academic_models import AcademicCycle
from .school_profiles import CYCLE_LABELS
from .services import PERMISSIONS, effective_permissions, has_permission, owns_school
from .views import access, refuse, parse_body, log_event, may_delegate_finance, financial_grant_allowed, string
from .school_functions import positions_for_school, account_functions

# Delegated authority cannot manufacture further delegators or administrators.
DELEGATABLE = PERMISSIONS - {"school.members.write", "school.roles.manage", "school.settings.write"}


def class_cycle_choices(school):
    choices = {code: CYCLE_LABELS[code] for code in school.education_cycles or [] if code in CYCLE_LABELS}
    choices.update(AcademicCycle.objects.filter(school=school, active=True).values_list("code", "name"))
    return choices


def describe(grant):
    return {"id": str(grant.pk), "user_id": str(grant.member.user_id),
            "permissions": grant.permissions, "reason": grant.reason, "class_cycle": grant.class_cycle,
            "source_function": grant.source_function, "granted_by": str(grant.granted_by_id),
            "expires_at": grant.expires_at, "revoked_at": grant.revoked_at,
            "revoked_by": str(grant.revoked_by_id) if grant.revoked_by_id else None,
            "revocation_reason": grant.revocation_reason, "created_at": grant.created_at}


@require_http_methods(["GET", "POST", "DELETE"])
@authorized
def delegations(request, school_id, delegation_id=None):
    school, error = access(request, school_id)
    if error is not None:
        return error
    owner = owns_school(request.user, school)
    if not owner and not has_permission(request.user, school, "school.roles.manage"):
        return refuse()
    if request.method == "GET":
        return JsonResponse({"delegations": [describe(g) for g in PermissionDelegation.objects.filter(school=school).select_related("member").order_by("-created_at")[:500]], "available_permissions": sorted(DELEGATABLE), "class_cycles": class_cycle_choices(school)})
    data, error = parse_body(request)
    if error is not None:
        return error
    if not string(data.get("reason"), 240):
        return JsonResponse({"error": "Motif explicite requis."}, status=422)
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        owner = owns_school(request.user, school)
        if not owner and not has_permission(request.user, school, "school.roles.manage"):
            return refuse()
        if request.method == "DELETE":
            grant = PermissionDelegation.objects.filter(pk=delegation_id, school=school).first()
            if not grant:
                return JsonResponse({"error": "Délégation introuvable."}, status=404)
            if not may_delegate_finance(request.user, school, grant.permissions):
                return refuse()
            if grant.revoked_at is None:
                grant.revoked_at, grant.revoked_by = timezone.now(), request.user
                grant.revocation_reason = data["reason"].strip()
                grant.save(update_fields=["revoked_at", "revoked_by", "revocation_reason"])
                log_event(school, request, "delegation_revoked", grant.pk)
            return JsonResponse(describe(grant))
        perms = data.get("permissions")
        if not isinstance(perms, list) or not perms or any(not isinstance(p, str) for p in perms) or not set(perms) <= DELEGATABLE:
            return JsonResponse({"error": "Permissions délégables invalides."}, status=422)
        class_cycle = data.get("class_cycle", "")
        if not isinstance(class_cycle, str) or (class_cycle and (
            set(perms) != {"school.classes.manage"} or class_cycle not in class_cycle_choices(school)
        )):
            return JsonResponse({"error": "Un cycle peut limiter une délégation réservée à la gestion des classes."}, status=422)
        if not may_delegate_finance(request.user, school, perms) or (not owner and not set(perms) <= effective_permissions(request.user, school)
                and not (set(perms) == {"school.classes.manage"} and has_permission(request.user, school, "school.academic.manage"))):
            return refuse()
        try:
            member = SchoolMember.objects.select_related("user").filter(school=school, user_id=data.get("user_id"), active=True).first()
        except (ValueError, ValidationError):
            member = None
        if not member:
            return JsonResponse({"error": "Compte actif de cet établissement requis."}, status=422)
        if not financial_grant_allowed(request.user, school, member.user, perms):
            return refuse()
        combined = effective_permissions(member.user, school) | set(perms)
        if "school.finance.receive" in combined and combined.intersection({"school.finance.approve", "school.finance.reverse"}):
            return JsonResponse({"error": "Séparez encaissement et validation/annulation financière."}, status=422)
        source = data.get("source_function", "")
        if not isinstance(source, str) or (source and source not in {p["code"] for p in positions_for_school(school)}):
            return JsonResponse({"error": "Fonction déléguée incompatible."}, status=422)
        expires = data.get("expires_at")
        try:
            end = parse_datetime(expires) if isinstance(expires, str) else None
            if expires is not None and (end is None or timezone.is_naive(end) or end <= timezone.now()):
                raise ValueError()
        except (ValueError, TypeError):
            return JsonResponse({"error": "Échéance future avec fuseau horaire requise."}, status=422)
        grant = PermissionDelegation.objects.create(school=school, member=member, permissions=sorted(set(perms)), reason=data["reason"].strip(), source_function=source, class_cycle=class_cycle, expires_at=end, granted_by=request.user)
        log_event(school, request, "delegation_granted", grant.pk)
    return JsonResponse(describe(grant), status=201)


@require_http_methods(["GET", "PATCH"])
@authorized
def functions(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not owns_school(request.user, school) and not has_permission(request.user, school, "school.members.write"):
        return refuse()
    if request.method == "PATCH":
        data, error = parse_body(request)
        if error is not None:
            return error
        codes = data.get("enabled_functions")
        options = {p["code"] for p in positions_for_school(school)}
        if not isinstance(codes, list) or any(not isinstance(c, str) for c in codes) or not set(codes) <= options:
            return JsonResponse({"error": "Fonctions incompatibles."}, status=422)
        with transaction.atomic():
            school = School.objects.select_for_update().get(pk=school.pk)
            before = school.enabled_functions
            school.enabled_functions = sorted(set(codes))
            school.save(update_fields=["enabled_functions"])
            log_event(school, request, "functions_configured", school.pk, {"before": before, "after": school.enabled_functions})
    return JsonResponse({"options": positions_for_school(school), "functions": account_functions(school)})
