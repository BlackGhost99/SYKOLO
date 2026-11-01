import json
import re

from django.contrib.auth import get_user_model
from django.core.exceptions import RequestDataTooBig
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods
from accounts.views import authorized
from pedagogy.domain import ValidationError as PolicyValidationError, validate_policy

from .models import (
    Organization, OrganizationMember, School, SchoolAudit, SchoolMember,
    SchoolRole, SchoolSetting,
)
from .services import (
    PERMISSIONS, ROLE_TEMPLATES, has_permission, key_for_scope,
    owns_organization, resolve_settings, school_access, school_response,
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


def log_event(school, request, event, subject=""):
    SchoolAudit.objects.create(
        school=school, actor=request.user, event=event, subject=str(subject)[:100]
    )


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
        log_event(school, request, "school_created")
    return JsonResponse(school_response(school), status=201)


@require_GET
@authorized
def schools(request):
    rows = School.objects.filter(
        Q(organization__members__user=request.user, organization__members__role="founder")
        | Q(members__user=request.user, members__active=True),
        is_active=True,
    ).distinct().order_by("name")[:100]
    return JsonResponse({"schools": [school_response(s) for s in rows]})


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
            {"user_id": str(m.user_id), "username": m.user.username,
             "role": m.role.code}
            for m in rows
        ]})
    data, error = parse_body(request)
    if error is not None:
        return error
    if not string(data.get("username"), 150) or not string(data.get("role"), 48):
        return JsonResponse({"error": "Identifiant ou rôle invalide."}, status=422)
    user = get_user_model().objects.filter(username=data["username"].strip(), is_active=True).first()
    role = SchoolRole.objects.filter(school=school, code=data["role"]).first()
    if user is None or role is None:
        return JsonResponse({"error": "Compte ou rôle introuvable."}, status=404)
    with transaction.atomic():
        member, created = SchoolMember.objects.update_or_create(
            school=school, user=user, defaults={"role": role, "active": True}
        )
        log_event(school, request, "member_added" if created else "member_role_changed", str(user.id))
    return JsonResponse({"user_id": str(user.id), "role": role.code}, status=201 if created else 200)


def role_response(role):
    return {"id": str(role.id), "code": role.code, "label": role.label,
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
        return JsonResponse({"roles": [role_response(r) for r in school.roles.order_by("code")]})
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
    member = SchoolMember.objects.select_related("role").get(school=school, user=request.user, active=True)
    if not set(perms) <= set(member.role.permissions):
        return refuse()
    try:
        # A savepoint keeps the outer request/test transaction usable after uniqueness errors.
        with transaction.atomic():
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
    member = SchoolMember.objects.select_related("role").get(school=school, user=request.user, active=True)
    if not set(perms) <= set(member.role.permissions):
        return refuse()
    with transaction.atomic():
        role = SchoolRole.objects.select_for_update().filter(school=school, id=role_id).first()
        if role is None:
            return JsonResponse({"error": "Rôle introuvable."}, status=404)
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
            obj = SchoolSetting.objects.create(school=school, scope_key=key, scope=scope, values=values)
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
        {"event": row.event, "subject": row.subject, "at": row.created_at.isoformat()}
        for row in rows
    ]})
