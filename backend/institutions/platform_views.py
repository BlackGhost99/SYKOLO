"""Platform-only provisioning; never exposed to school administrators."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized
from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES, school_response
from .views import parse_body, log_event, string


def platform_only(request):
    return bool(request.user.is_superuser and request.session.get("mfa_verified", False))


@require_http_methods(["GET", "POST"])
@authorized
def platform_schools(request):
    if not platform_only(request):
        return JsonResponse({"error": "Accès réservé au super-administrateur avec MFA."}, status=403)
    if request.method == "GET":
        rows = School.objects.select_related("organization").order_by("name")[:300]
        return JsonResponse({"schools": [
            {**school_response(row), "organization": row.organization.name, "active": row.is_active,
             "members_count": row.members.filter(active=True).count()}
            for row in rows
        ], "total": School.objects.count(), "organizations": Organization.objects.count(),
        "users": get_user_model().objects.count(),
        "organization_options": [{"id": str(o.pk), "name": o.name} for o in Organization.objects.order_by("name")[:300]]})

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
    username, email = data.get("username"), data.get("email")
    first_name, last_name = data.get("first_name", ""), data.get("last_name", "")
    password, role_code = data.get("password"), data.get("role", "direction")
    if not all((existing_org is not None or string(org_name, 180), string(school_name, 180),
                string(username, 150), string(email, 254), "@" in email if isinstance(email, str) else False,
                isinstance(first_name, str) and len(first_name) <= 150,
                isinstance(last_name, str) and len(last_name) <= 150)):
        return JsonResponse({"error": "Données de l'établissement ou du compte invalides."}, status=422)
    if role_code not in {"direction", "proprietaire"}:
        return JsonResponse({"error": "Responsable initial : propriétaire ou direction uniquement."}, status=422)
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
            user = User.objects.create_user(username=candidate.username, email=candidate.email,
                                            first_name=candidate.first_name, last_name=candidate.last_name,
                                            password=password)
            # Un propriétaire nommé pour une école existante ne devient pas propriétaire de tout le groupe.
            if role_code == "proprietaire" and existing_org is None:
                OrganizationMember.objects.create(organization=org, user=user, role="founder")
            school = School.objects.create(organization=org, name=school_name.strip())
            templates = list(ROLE_TEMPLATES)
            if role_code == "proprietaire":
                direction_perms = next(perms for code, _, perms in templates if code == "direction")
                templates.append(("proprietaire", "Propriétaire", direction_perms))
            roles = {role.code: role for role in SchoolRole.objects.bulk_create([
                SchoolRole(school=school, code=code, label=label, permissions=perms)
                for code, label, perms in templates
            ])}
            SchoolMember.objects.create(school=school, user=user, role=roles[role_code])
            log_event(school, request, "school_provisioned", str(user.pk))
    except IntegrityError:
        return JsonResponse({"error": "Cet identifiant existe déjà."}, status=409)
    return JsonResponse({**school_response(school), "organization": org.name,
                         "username": user.username, "role": role_code}, status=201)


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
    if not all((string(username, 150), string(email, 254), isinstance(email, str) and "@" in email,
                isinstance(first_name, str) and len(first_name) <= 150,
                isinstance(last_name, str) and len(last_name) <= 150, isinstance(password, str))):
        return JsonResponse({"error": "Données du compte invalides."}, status=422)
    role = SchoolRole.objects.filter(school=school, code=code).first()
    if role is None:
        return JsonResponse({"error": "Rôle non disponible pour cette école."}, status=422)
    User = get_user_model()
    candidate = User(username=username.strip(), email=email.strip(), first_name=first_name.strip(), last_name=last_name.strip())
    try:
        validate_password(password, user=candidate)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=422)
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=candidate.username, email=candidate.email,
                                            first_name=candidate.first_name, last_name=candidate.last_name,
                                            password=password)
            SchoolMember.objects.create(school=school, user=user, role=role)
            log_event(school, request, "member_account_created", str(user.pk))
    except IntegrityError:
        return JsonResponse({"error": "Cet identifiant existe déjà."}, status=409)
    return JsonResponse({"username": user.username, "role": role.code}, status=201)


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
            defaults={"role": role, "active": True}
        )
        log_event(school, request, "platform_admin_school_access", str(request.user.pk))
    return JsonResponse({"school_id": str(school.id), "access": "direction"})
