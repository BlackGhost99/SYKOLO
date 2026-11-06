from uuid import uuid4
import json
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.exceptions import RequestDataTooBig
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods
from accounts.views import authorized
from pedagogy.domain import ValidationError as PolicyValidationError, validate_policy

from .school_functions import account_function_codes
from .models import (
    Organization, OrganizationMember, School, SchoolAudit, SchoolMember, SchoolLogin,
    SchoolRole, SchoolSetting,
)
from .services import (
    PERMISSIONS, ROLE_TEMPLATES, has_permission, effective_permissions, key_for_scope,
    owns_organization, resolve_settings, school_access, school_response, quota_reached, public_role_label,
    validate_scope,
)


def parse_body(request):
    if request.content_type != "application/json":
        return None, JsonResponse({"error": "JSON requis."}, status=415)
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > 32768:
            raise RequestDataTooBig()
        raw = request.body
        if len(raw) > 32768:
            raise RequestDataTooBig()
        data = json.loads(raw)
    except RequestDataTooBig:
        return None, JsonResponse({"error": "Requête trop volumineuse."}, status=413)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None, JsonResponse({"error": "JSON invalide."}, status=400)
    if not isinstance(data, dict):
        return None, JsonResponse({"error": "Objet JSON requis."}, status=400)
    return data, None


def refuse():
    return JsonResponse({"error": "Permission insuffisante."}, status=403)


def access(request, school_id):
    school = school_access(request.user, school_id)
    if not school:
        return None, JsonResponse({"error": "Établissement introuvable."}, status=404)
    return school, None


def string(value, max_len):
    return isinstance(value, str) and 0 < len(value.strip()) <= max_len


def log_event(school, request, event, subject="", details=None):
    SchoolAudit.objects.create(
        school=school, actor=request.user, event=event, subject=str(subject)[:100], details=details or {}
    )


# Financial approvals must not be minted by the person who will control them.
# This applies to primary and additional roles, including a founder who is
# also the school's director. Routine non-financial appointments stay editable.
FINANCIAL_DUTIES = frozenset({
    "school.finance.manage", "school.finance.receive", "school.finance.reverse",
    "school.finance.approve", "school.finance.deposit",
})


def financial_grant_allowed(actor, school, target, permissions):
    requested = set(permissions) & FINANCIAL_DUTIES
    if not requested:
        return True
    existing = (
        effective_permissions(target, school) & FINANCIAL_DUTIES
        if target is not None else set()
    )
    added = requested - existing
    if not added:
        return True
    return (owns_organization(actor, school.organization)
            and target is not None and actor.pk != target.pk)


def financial_role_change_allowed(actor, school, role, permissions):
    before = set(role.permissions) & FINANCIAL_DUTIES
    after = set(permissions) & FINANCIAL_DUTIES
    if before == after:
        return True
    if not owns_organization(actor, school.organization):
        return False
    if after - before:
        # A founder may delegate to staff but must not change a role already
        # assigned to their own account to acquire a new financial power.
        return not SchoolMember.objects.filter(
            Q(role=role) | Q(additional_roles=role),
            school=school, user=actor, active=True
        ).exists()
    return True


@require_http_methods(["GET", "POST"])
@authorized
def organizations(request):
    if request.method == "GET":
        rows = Organization.objects.filter(members__user=request.user, members__role="founder").order_by("name")
        return JsonResponse({"organizations": [
            {"id": str(row.id), "name": row.name} for row in rows[:100]
        ]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if not string(data.get("name"), 180):
        return JsonResponse({"error": "Nom d'organisation invalide."}, status=422)
    with transaction.atomic():
        org = Organization.objects.create(name=data["name"].strip())
        OrganizationMember.objects.create(organization=org, user=request.user, role="founder")
    return JsonResponse({"id": str(org.id), "name": org.name}, status=201)


@require_http_methods(["GET", "POST"])
@authorized
def organization_schools(request, organization_id):
    org = Organization.objects.filter(pk=organization_id, members__user=request.user, members__role="founder").first()
    if org is None:
        return JsonResponse({"error": "Organisation introuvable."}, status=404)
    if request.method == "GET":
        return JsonResponse({"schools": [school_response(s) for s in org.schools.order_by("name")]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if not string(data.get("name"), 180):
        return JsonResponse({"error": "Nom de l'établissement invalide."}, status=422)
    short_name = data.get("short_name", "")
    color = data.get("primary_color", "#1B664C")
    if not isinstance(short_name, str) or len(short_name) > 60 or not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        return JsonResponse({"error": "Identité visuelle invalide."}, status=422)
    with transaction.atomic():
        school = School.objects.create(
            organization=org, name=data["name"].strip(),
            short_name=short_name.strip(), primary_color=color,
        )
        SchoolRole.objects.bulk_create([
            SchoolRole(school=school, code=code, label=label, permissions=permissions)
            for code, label, permissions in ROLE_TEMPLATES
        ])
        SchoolLogin.objects.get_or_create(school=school, user=request.user, defaults={"username": request.user.username})
        log_event(school, request, "school_created")
    return JsonResponse(school_response(school), status=201)


@require_GET
@authorized
def schools(request):
    rows = School.objects.filter(
        Q(organization__members__user=request.user, organization__members__role="founder")
        | Q(members__user=request.user, members__active=True),
        is_active=True,
    ).distinct().order_by("name")
    if request.session.get("school_id"):
        rows = rows.filter(pk=request.session["school_id"])
    return JsonResponse({"schools": [school_response(s) for s in rows[:100]]})


@require_GET
@authorized
def school_detail(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    return JsonResponse(school_response(school))


@require_http_methods(["GET", "POST"])
@authorized
def school_members(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    perm = "school.members.read" if request.method == "GET" else "school.members.write"
    if not has_permission(request.user, school, perm):
        return refuse()
    if request.method == "GET":
        rows = SchoolMember.objects.select_related("user", "role").filter(
            school=school, active=True
        ).order_by("user__username")[:200]
        return JsonResponse({"members": [
            {"user_id": str(m.user_id), "username": SchoolLogin.objects.filter(school=school, user=m.user).values_list("username", flat=True).first() or m.user.username,
             "function_codes": account_function_codes(school, m.function_codes),
             "role": m.role.code, "additional_roles": list(m.additional_roles.filter(school=school).values_list("code", flat=True))}
            for m in rows
        ]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if not string(data.get("username"), 150) or not string(data.get("role"), 48):
        return JsonResponse({"error": "Identifiant ou rôle invalide."}, status=422)
    identity = SchoolLogin.objects.filter(school=school, username=data["username"].strip(), user__is_active=True).first()
    user = identity.user if identity else get_user_model().objects.filter(
        username=data["username"].strip(), is_active=True).filter(
        Q(schoolmember__school=school) | Q(schoolmember__isnull=True)
    ).first()
    role = SchoolRole.objects.filter(school=school, code=data["role"]).first()
    if user is None or role is None:
        return JsonResponse({"error": "Compte ou rôle introuvable."}, status=404)
    codes = data.get("additional_roles", [])
    if not isinstance(codes, list) or not all(isinstance(code, str) for code in codes) or len(codes) > 20:
        return JsonResponse({"error": "Fonctions supplémentaires invalides."}, status=422)
    extra = list(SchoolRole.objects.filter(school=school, code__in=set(codes)))
    if len(extra) != len(set(codes)):
        return JsonResponse({"error": "Fonction étrangère ou inconnue."}, status=422)
    granted = set().union(*(set(r.permissions) for r in [role, *extra]))
    if not may_delegate_finance(request.user, school, granted):
        return refuse()
    if not owns_organization(request.user, school.organization) and not granted <= effective_permissions(request.user, school):
        return refuse()
    from .school_functions import validate_account_functions
    try:
        functions = validate_account_functions(school, data.get("function_codes", []))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        # Match main #45: recompute financial duties under the school lock.
        role = SchoolRole.objects.get(pk=role.pk, school=school)
        extra = list(SchoolRole.objects.filter(school=school, code__in=set(codes)))
        granted = set().union(*(set(r.permissions) for r in [role, *extra]))
        if not owns_organization(request.user, school.organization) and not granted <= effective_permissions(request.user, school):
            return refuse()
        if not financial_grant_allowed(request.user, school, user, granted):
            return refuse()
        previous = SchoolMember.objects.filter(school=school, user=user).first()
        before = {"role": previous.role.code, "additional_roles": list(previous.additional_roles.values_list("code", flat=True)), "functions": previous.function_codes} if previous else {}
        member, created = SchoolMember.objects.update_or_create(
            school=school, user=user, defaults={"role": role, "active": True}
        )
        SchoolLogin.objects.get_or_create(school=school, user=user, defaults={"username": data["username"].strip()})
        if "additional_roles" in data:
            member.additional_roles.set(extra)
        if "function_codes" in data:
            member.function_codes = functions
            member.save(update_fields=["function_codes"])
        log_event(school, request, "member_added" if created else "member_role_changed", str(user.id), {"before": before, "after": {"role": role.code, "additional_roles": list(member.additional_roles.values_list("code", flat=True)), "functions": member.function_codes}})
    return JsonResponse({"user_id": str(user.id), "role": role.code}, status=201 if created else 200)



@require_GET
@authorized
def my_school_access(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    member = SchoolMember.objects.select_related("role").filter(
        school=school, user=request.user, active=True
    ).first()
    founder = owns_organization(request.user, school.organization)
    return JsonResponse({
        "school": school_response(school),
        "role": member.role.code if member else ("proprietaire" if founder else None),
        "role_label": public_role_label(member.role, school) if member else ("Propriétaire" if founder else ""),
        "roles": [member.role.code, *member.additional_roles.filter(school=school).values_list("code", flat=True)] if member else [],
        "permissions": sorted(effective_permissions(request.user, school)) if member else (["school.view", "school.members.write"] if founder else []),
    })


@require_http_methods(["POST"])
@authorized
def school_user_create(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.members.write"):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    username, email = data.get("username"), data.get("email")
    first_name, last_name = data.get("first_name", ""), data.get("last_name", "")
    password, role_code = data.get("password"), data.get("role")
    if not (string(username, 150) and string(email, 254) and "@" in email
            and isinstance(first_name, str) and len(first_name) <= 150
            and isinstance(last_name, str) and len(last_name) <= 150
            and isinstance(password, str) and string(role_code, 48)):
        return JsonResponse({"error": "Données du nouveau compte invalides."}, status=422)
    role = SchoolRole.objects.filter(school=school, code=role_code).first()
    if role is None:
        return JsonResponse({"error": "Rôle introuvable dans cet établissement."}, status=404)
    if not may_delegate_finance(request.user, school, role.permissions):
        return refuse()
    if not owns_organization(request.user, school.organization):
        actor = SchoolMember.objects.select_related("role").filter(
            school=school, user=request.user, active=True
        ).first()
        if actor is None or not set(role.permissions).issubset(effective_permissions(request.user, school)):
            return refuse()
    User = get_user_model()
    candidate = User(username=username.strip(), email=email.strip(),
                     first_name=first_name.strip(), last_name=last_name.strip())
    try:
        validate_password(password, user=candidate)
    except DjangoValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=422)
    from .school_functions import validate_account_functions
    try:
        functions = validate_account_functions(school, data.get("function_codes", []))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            role = SchoolRole.objects.get(pk=role.pk, school=school)
            if not may_delegate_finance(request.user, school, role.permissions):
                return refuse()
            if not owns_organization(request.user, school.organization) and not set(role.permissions) <= effective_permissions(request.user, school):
                return refuse()
            if quota_reached(school, "users"):
                return JsonResponse({"error": "Plafond d'utilisateurs atteint pour cet établissement."}, status=409)
            user = User.objects.create_user(username=(candidate.username if not User.objects.filter(username=candidate.username).exists() else "school-" + uuid4().hex), email=candidate.email,
                                           first_name=candidate.first_name, last_name=candidate.last_name,
                                           password=password)
            SchoolMember.objects.create(school=school, user=user, role=role, function_codes=functions)
            SchoolLogin.objects.create(school=school, user=user, username=username.strip())
            log_event(school, request, "member_account_created", str(user.pk))
    except IntegrityError:
        return JsonResponse({"error": "Cet identifiant est déjà utilisé."}, status=409)
    return JsonResponse({"username": username.strip(), "role": role.code}, status=201)

def may_delegate_finance(user, school, permissions):
    return not FINANCIAL_DUTIES.intersection(permissions) or owns_organization(user, school.organization)


def role_response(role, school=None):
    return {"id": str(role.id), "code": role.code, "label": public_role_label(role, school),
            "permissions": role.permissions, "revision": role.revision}


@require_http_methods(["GET", "POST"])
@authorized
def school_roles(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        if not has_permission(request.user, school, "school.roles.read") and not owns_organization(request.user, school.organization):
            return refuse()
        from .school_functions import account_functions, suggested_account_function
        functions = account_functions(school)
        return JsonResponse({"functions": functions, "roles": [
            {**role_response(r, school), "suggested_function": suggested_account_function(school, r.code, functions)}
            for r in school.roles.order_by("code")
        ],
                             "available_permissions": sorted(PERMISSIONS)})
    if not has_permission(request.user, school, "school.roles.manage"):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    code, label, perms = data.get("code"), data.get("label"), data.get("permissions")
    if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,47}", code) or not string(label, 100):
        return JsonResponse({"error": "Code ou intitulé invalide."}, status=422)
    if not isinstance(perms, list) or not all(isinstance(x, str) for x in perms) or not set(perms) <= PERMISSIONS:
        return JsonResponse({"error": "Permissions inconnues."}, status=422)
    if not set(perms) <= effective_permissions(request.user, school):
        return refuse()
    if not may_delegate_finance(request.user, school, perms):
        return refuse()
    try:
        # A savepoint keeps the outer request/test transaction usable after uniqueness errors.
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            if not set(perms) <= effective_permissions(request.user, school):
                return refuse()
            if not may_delegate_finance(request.user, school, perms):
                return refuse()
            role = SchoolRole.objects.create(
                school=school, code=code, label=label.strip(), permissions=sorted(set(perms))
            )
    except IntegrityError:
        return JsonResponse({"error": "Ce rôle existe déjà."}, status=409)
    log_event(school, request, "role_created", role.code)
    return JsonResponse(role_response(role), status=201)


@require_http_methods(["PATCH"])
@authorized
def school_role_detail(request, school_id, role_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.roles.manage"):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    perms, label, revision = data.get("permissions"), data.get("label"), data.get("revision")
    if not isinstance(perms, list) or not all(isinstance(x, str) for x in perms) or not set(perms) <= PERMISSIONS or not string(label, 100):
        return JsonResponse({"error": "Rôle invalide."}, status=422)
    if type(revision) is not int or revision < 1:
        return JsonResponse({"error": "Révision invalide."}, status=422)
    if not set(perms) <= effective_permissions(request.user, school):
        return refuse()
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        role = SchoolRole.objects.select_for_update().filter(school=school, id=role_id).first()
        if role is None:
            return JsonResponse({"error": "Rôle introuvable."}, status=404)
        if not set(perms) <= effective_permissions(request.user, school):
            return refuse()
        if not may_delegate_finance(request.user, school, FINANCIAL_DUTIES.intersection(set(role.permissions) ^ set(perms))):
            return refuse()
        if not financial_role_change_allowed(request.user, school, role, perms):
            return refuse()
        if role.revision != revision:
            return JsonResponse({"error": "Conflit de version."}, status=409)
        role.label = label.strip()
        role.permissions = sorted(set(perms))
        role.revision += 1
        role.save(update_fields=["label", "permissions", "revision"])
        log_event(school, request, "role_updated", role.code)
    return JsonResponse(role_response(role))


@require_http_methods(["GET", "POST"])
@authorized
def school_settings(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    perm = "school.settings.read" if request.method == "GET" else "school.settings.write"
    if not has_permission(request.user, school, perm):
        return refuse()
    if request.method == "GET":
        try:
            context = validate_scope(dict(request.GET.items()))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=422)
        effective, layers = resolve_settings(school, context)
        return JsonResponse({"effective": effective, "layers": layers})
    data, error = parse_body(request)
    if error is not None:
        return error
    try:
        scope = validate_scope(data.get("scope", {}))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    values, expected = data.get("values"), data.get("revision")
    if not isinstance(values, dict) or not values or type(expected) is not int or expected < 0:
        return JsonResponse({"error": "Valeurs ou version invalides."}, status=422)
    if len(json.dumps(values, ensure_ascii=False)) > 16000:
        return JsonResponse({"error": "Paramètres trop volumineux."}, status=413)
    key = key_for_scope(scope)
    with transaction.atomic():
        obj = SchoolSetting.objects.select_for_update().filter(school=school, scope_key=key).first()
        current = obj.revision if obj else 0
        if current != expected:
            return JsonResponse({"error": "Conflit de version.", "revision": current}, status=409)
        effective, _ = resolve_settings(school, scope, replacement=(key, scope, values, current + 1))
        if "grading" in effective:
            try:
                validate_policy(effective["grading"])
            except (PolicyValidationError, TypeError, AttributeError, KeyError) as exc:
                return JsonResponse({"error": "Barème invalide : " + str(exc)}, status=422)
        if obj is None:
            try:
                with transaction.atomic():
                    obj = SchoolSetting.objects.create(school=school, scope_key=key, scope=scope, values=values)
            except IntegrityError:
                return JsonResponse({"error": "Conflit de version."}, status=409)
        else:
            obj.values = values
            obj.revision += 1
            obj.save(update_fields=["values", "revision", "updated_at"])
        log_event(school, request, "settings_updated", key)
    return JsonResponse({"scope": scope, "revision": obj.revision, "effective": effective})


@require_GET
@authorized
def school_audit(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.audit.read"):
        return refuse()
    rows = SchoolAudit.objects.filter(school=school)[:100]
    return JsonResponse({"events": [
        {"event": row.event, "subject": row.subject, "details": row.details, "at": row.created_at.isoformat()}
        for row in rows
    ]})
