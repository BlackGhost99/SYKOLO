"""Platform-only provisioning; never exposed to school administrators."""
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole, SchoolLogin
from .services import (
    OWNER_ROLE_CODE, SECONDARY_HEAD_CODES, platform_only, role_available, role_templates_for,
    school_response, quota_reached,
)
from .school_functions import account_functions, suggested_account_function, validate_account_functions
from .school_profiles import CYCLE_LABELS, profile_options, validate_school_profile
from .standard_classes import ensure_standard_levels
from .views import parse_body, log_event, string


@require_http_methods(["GET", "POST"])
@authorized
def platform_schools(request):
    if not platform_only(request):
        return JsonResponse({"error": "Accès réservé au super-administrateur avec MFA."}, status=403)
    if request.method == "GET":
        if "school_type" in request.GET:
            try:
                kind, cycles = validate_school_profile(request.GET["school_type"], request.GET.getlist("cycle"))
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=422)
            candidate = School(school_type=kind, education_cycles=cycles)
            roles = {code: label for code, label, _ in role_templates_for(candidate) if code not in {"parent", "eleve"}}
            head = SECONDARY_HEAD_CODES.get(kind)
            if head and head not in roles:
                head = "principal" if "principal" in roles else None
            if head:
                roles.pop("direction", None)
            return JsonResponse({"roles": [{"code": code, "label": label} for code, label in roles.items()],
                                 "default_role": head or "direction"})
        rows = School.objects.select_related("organization").order_by("name")[:300]
        return JsonResponse({"schools": [
            {**school_response(row), "organization": row.organization.name, "active": row.is_active,
             "members_count": row.members.filter(active=True, user__is_active=True, user__is_superuser=False).count()}
            for row in rows
        ], "total": School.objects.count(), "organizations": Organization.objects.count(),
        "users": get_user_model().objects.count(),
        "organization_options": [{"id": str(o.pk), "name": o.name} for o in Organization.objects.order_by("name")[:300]],
        "school_profiles": profile_options(), "cycle_labels": CYCLE_LABELS})

    data, error = parse_body(request)
    if error is not None:
        return error
    org_name, school_name = data.get("organization_name"), data.get("school_name")
    existing_org_id = data.get("organization_id")
    existing_org = None
    if existing_org_id:
        try:
            existing_org = Organization.objects.filter(pk=existing_org_id).first()
        except (ValueError, TypeError, ValidationError):
            existing_org = None
        if existing_org is None:
            return JsonResponse({"error": "Organisation existante introuvable."}, status=422)
    try:
        school_type, education_cycles = validate_school_profile(
            data.get("school_type"), data.get("education_cycles")
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    username, email = data.get("username"), data.get("email")
    first_name, last_name = data.get("first_name", ""), data.get("last_name", "")
    password, role_code = data.get("password"), data.get("role", "direction")
    if not all((existing_org is not None or string(org_name, 180), string(school_name, 180),
                string(username, 150), string(email, 254), "@" in email if isinstance(email, str) else False,
                isinstance(first_name, str) and len(first_name) <= 150,
                isinstance(last_name, str) and len(last_name) <= 150)):
        return JsonResponse({"error": "Données de l'établissement ou du compte invalides."}, status=422)
    templates = role_templates_for(School(school_type=school_type, education_cycles=education_cycles))
    if not isinstance(role_code, str) or role_code not in {code for code, _, _ in templates} - {"parent", "eleve"}:
        return JsonResponse({"error": "Rôle initial incompatible avec le type ou les cycles de l’établissement."}, status=422)
    if not isinstance(password, str):
        return JsonResponse({"error": "Mot de passe requis."}, status=422)
    User = get_user_model()
    candidate = User(username=username.strip(), email=email.strip(), first_name=first_name.strip(), last_name=last_name.strip())
    try:
        validate_password(password, user=candidate)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=422)
    try:
        with transaction.atomic():
            # One explicit organization per provisioning request; no accidental cross-school sharing.
            org = existing_org if existing_org is not None else Organization.objects.create(name=org_name.strip())
            user = User.objects.create_user(username=(candidate.username if not User.objects.filter(username=candidate.username).exists() else "school-" + uuid4().hex), email=candidate.email,
                                            first_name=candidate.first_name, last_name=candidate.last_name,
                                            password=password)
            # Un propriétaire nommé pour une école existante ne devient pas propriétaire de tout le groupe.
            if role_code == OWNER_ROLE_CODE and existing_org is None:
                OrganizationMember.objects.create(organization=org, user=user, role="founder")
            school = School.objects.create(
                organization=org, name=school_name.strip(),
                school_type=school_type, education_cycles=education_cycles,
            )
            ensure_standard_levels(school)
            roles = {role.code: role for role in SchoolRole.objects.bulk_create([
                SchoolRole(school=school, code=code, label=label, permissions=perms)
                for code, label, perms in templates
            ])}
            initial_function = suggested_account_function(school, role_code, account_functions(school))
            SchoolMember.objects.create(
                school=school, user=user, role=roles[role_code],
                is_school_owner=role_code == OWNER_ROLE_CODE,
                function_codes=[initial_function] if initial_function else [],
            )
            SchoolLogin.objects.create(school=school, user=user, username=username.strip())
            log_event(school, request, "school_provisioned", str(user.pk))
    except IntegrityError:
        return JsonResponse({"error": "Cet identifiant existe déjà."}, status=409)
    return JsonResponse({**school_response(school), "organization": org.name,
                         "username": username.strip(), "role": role_code}, status=201)


@require_http_methods(["POST"])
@authorized
def platform_add_user(request, school_id):
    if not platform_only(request):
        return JsonResponse({"error": "Accès réservé au super-administrateur avec MFA."}, status=403)
    school = School.objects.filter(pk=school_id, is_active=True).first()
    if school is None:
        return JsonResponse({"error": "Établissement introuvable."}, status=404)
    data, error = parse_body(request)
    if error is not None:
        return error
    username, email, password, code = data.get("username"), data.get("email"), data.get("password"), data.get("role")
    first_name, last_name = data.get("first_name", ""), data.get("last_name", "")
    if not all((string(username, 150), string(email, 254), isinstance(email, str) and "@" in email, string(code, 48),
                isinstance(first_name, str) and len(first_name) <= 150,
                isinstance(last_name, str) and len(last_name) <= 150, isinstance(password, str))):
        return JsonResponse({"error": "Données du compte invalides."}, status=422)
    User = get_user_model()
    candidate = User(username=username.strip(), email=email.strip(), first_name=first_name.strip(), last_name=last_name.strip())
    try:
        validate_password(password, user=candidate)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=422)
    try:
        with transaction.atomic():
            school = School.objects.select_for_update().get(pk=school.pk)
            if not school.is_active:
                return JsonResponse({"error": "Établissement introuvable."}, status=404)
            role = SchoolRole.objects.filter(school=school, code=code).first()
            if role is None or not role_available(school, code):
                return JsonResponse({"error": "Rôle non disponible pour cette école."}, status=422)
            functions = validate_account_functions(school, data.get("function_codes", []))
            if quota_reached(school, "users"):
                return JsonResponse({"error": "Plafond d'utilisateurs atteint pour cet établissement."}, status=409)
            user = User.objects.create_user(username=(candidate.username if not User.objects.filter(username=candidate.username).exists() else "school-" + uuid4().hex), email=candidate.email,
                                            first_name=candidate.first_name, last_name=candidate.last_name,
                                            password=password)
            SchoolMember.objects.create(school=school, user=user, role=role, function_codes=functions,
                                        is_school_owner=role.code == OWNER_ROLE_CODE)
            SchoolLogin.objects.create(school=school, user=user, username=username.strip())
            log_event(school, request, "member_account_created", str(user.pk))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except IntegrityError:
        return JsonResponse({"error": "Cet identifiant existe déjà."}, status=409)
    return JsonResponse({"username": username.strip(), "role": role.code}, status=201)


@require_http_methods(["POST"])
@authorized
def platform_assume_school_administration(request, school_id):
    """Explicit, audited association before platform staff can work inside an institution."""
    if not platform_only(request):
        return JsonResponse({"error": "Accès réservé au super-administrateur avec MFA."}, status=403)
    school = School.objects.filter(pk=school_id, is_active=True).first()
    if school is None:
        return JsonResponse({"error": "Établissement introuvable."}, status=404)
    with transaction.atomic():
        role = SchoolRole.objects.filter(school=school, code="direction").first()
        if role is None:
            return JsonResponse({"error": "Rôle direction introuvable."}, status=409)
        SchoolMember.objects.update_or_create(
            school=school, user=request.user,
            defaults={"role": role, "active": True, "access_cycle_ids": None}
        )
        log_event(school, request, "platform_admin_school_access", str(request.user.pk))
    return JsonResponse({"school_id": str(school.id), "access": "direction"})
