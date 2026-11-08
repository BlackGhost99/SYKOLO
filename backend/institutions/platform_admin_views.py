"""API de pilotage YEM. Reserved to MFA-verified platform super-admins."""
from uuid import UUID
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from accounts.views import authorized
from .models import (
    Organization, PlatformAudit, School, SchoolAdminPolicy,
    SchoolAudit, SchoolMember, SchoolRole, Student,
)
from .platform_views import platform_only
from .services import OWNER_ROLE_CODE, provision_appointment_roles, public_role_label, role_available
from .school_profiles import validate_school_profile
from .views import parse_body, log_event, string


def denied():
    return JsonResponse({"error": "Accès super-administrateur et MFA requis."}, status=403)


def audit(request, event, subject, school=None, reason=""):
    PlatformAudit.objects.create(
        actor=request.user, school=school, event=event,
        subject=str(subject)[:180], reason=str(reason)[:240],
    )


def size(value, default=1, upper=10000):
    try:
        return min(max(int(value), 1), upper)
    except (TypeError, ValueError, OverflowError):
        return default


def summary(school):
    return {
        "id": str(school.pk), "name": school.name,
        "school_type": school.school_type,
        "school_type_label": school.get_school_type_display(),
        "education_cycles": school.education_cycles,
        "organization": school.organization.name,
        "organization_id": str(school.organization_id),
        "members_count": school.members_count,
        "students_count": school.students_count,
        "active": school.is_active,
        "created_at": school.created_at.isoformat(),
    }


def directory():
    return School.objects.select_related("organization").annotate(
        members_count=Count(
            "members", filter=Q(members__active=True, members__user__is_active=True, members__user__is_superuser=False), distinct=True
        ),
        students_count=Count("students", filter=Q(students__active=True), distinct=True),
    )


def audit_item(row, *, source):
    if source == "platform":
        return {
            "id": str(row.pk), "event": row.event, "subject": row.subject,
            "reason": row.reason, "school_id": str(row.school_id) if row.school_id else None,
            "school": row.school.name if row.school else "",
            "actor": row.actor.username if row.actor else "Compte supprimé",
            "at": row.created_at.isoformat(), "source": source,
        }
    return {
        "id": str(row.pk), "event": row.event, "subject": row.subject,
        "reason": "", "school_id": str(row.school_id),
        "school": row.school.name, "actor": row.actor.username if row.actor else "Compte supprimé",
        "at": row.created_at.isoformat(), "source": source,
    }


def recent_events(limit=12, school_id=None):
    platform = PlatformAudit.objects.select_related("actor", "school").all()
    school = SchoolAudit.objects.select_related("actor", "school").exclude(
        event__in=("member_role_changed", "member_reactivated", "member_suspended",
                   "school_reactivated", "school_suspended")
    )
    if school_id:
        platform = platform.filter(school_id=school_id)
        school = school.filter(school_id=school_id)
    results = [audit_item(r, source="platform") for r in platform[:limit]]
    results += [audit_item(r, source="school") for r in school[:limit]]
    results.sort(key=lambda row: row["at"], reverse=True)
    return results[:limit]


@require_GET
@authorized
def platform_dashboard(request):
    if not platform_only(request):
        return denied()

    q = str(request.GET.get("q", "")).strip()[:100]
    organization = str(request.GET.get("organization", "")).strip()
    status = str(request.GET.get("status", "all")).strip()
    sort = str(request.GET.get("sort", "name")).strip()
    page = size(request.GET.get("page"), default=1)
    per_page = size(request.GET.get("per_page"), default=5, upper=20)
    schools = directory()
    if q:
        schools = schools.filter(
            Q(name__icontains=q) | Q(organization__name__icontains=q)
        )
    if organization:
        schools = schools.filter(organization_id=organization) if organization in {
            str(id) for id in Organization.objects.values_list("id", flat=True)
        } else schools.none()
    if status == "active":
        schools = schools.filter(is_active=True)
    if status == "inactive":
        schools = schools.filter(is_active=False)

    sorts = {
        "name": ("name", "pk"), "-name": ("-name", "pk"),
        "recent": ("-created_at", "pk"), "oldest": ("created_at", "pk"),
        "members": ("-members_count", "name"),
    }
    schools = schools.order_by(*sorts.get(sort, sorts["name"]))
    total_filtered = schools.count()
    pages = max(1, (total_filtered + per_page - 1) // per_page)
    page = min(page, pages)
    start = (page - 1) * per_page
    rows = list(schools[start:start + per_page])
    orgs = Organization.objects.annotate(
        schools_count=Count("schools", distinct=True),
    ).order_by("name")
    school_total = School.objects.count()
    return JsonResponse({
        "organizations": Organization.objects.count(),
        "schools_total": school_total,
        "schools_active": School.objects.filter(is_active=True).count(),
        "schools_inactive": School.objects.filter(is_active=False).count(),
        "users_active": get_user_model().objects.filter(
            is_active=True, is_superuser=False, schoolmember__active=True,
            schoolmember__school__is_active=True,
        ).distinct().count(),
        "schools": [summary(s) for s in rows],
        "filtered_total": total_filtered, "page": page, "pages": pages,
        "per_page": per_page,
        "organization_options": [
            {"id": str(o.pk), "name": o.name, "schools_count": o.schools_count}
            for o in orgs[:500]
        ],
        "recent_events": recent_events(5),
    })


@require_http_methods(["GET", "POST"])
@authorized
def platform_organizations(request):
    if not platform_only(request):
        return denied()
    if request.method == "GET":
        qs = Organization.objects.annotate(
            schools_count=Count("schools", distinct=True),
        ).order_by("name")
        return JsonResponse({"organizations": [
            {"id": str(o.pk), "name": o.name, "schools_count": o.schools_count}
            for o in qs[:500]
        ]})
    body, error = parse_body(request)
    if error is not None:
        return error
    name = body.get("name")
    if not string(name, 180):
        return JsonResponse({"error": "Nom de l'organisation invalide."}, status=422)
    name = name.strip()
    with transaction.atomic():
        if Organization.objects.filter(name__iexact=name).exists():
            return JsonResponse({"error": "Une organisation de ce nom existe déjà."}, status=409)
        org = Organization.objects.create(name=name)
        audit(request, "organization_created", name)
    return JsonResponse({"id": str(org.pk), "name": org.name}, status=201)


def detail_dict(s):
    from .school_functions import account_functions, suggested_account_function
    policy = SchoolAdminPolicy.objects.filter(school=s).first()
    members = SchoolMember.objects.filter(school=s).select_related("user", "role").order_by(
        "user__last_name", "user__username"
    )
    roles = SchoolRole.objects.filter(school=s).order_by("label")
    functions = account_functions(s)
    return {
        "school": {
            "id": str(s.id), "name": s.name, "active": s.is_active,
            "school_type": s.school_type,
            "school_type_label": s.get_school_type_display(),
            "education_cycles": s.education_cycles,
            "organization": s.organization.name,
            "organization_id": str(s.organization_id),
            "created_at": s.created_at.isoformat(),
        },
        "functions": functions,
        "login_code": str(s.pk),
        "members_count": members.filter(active=True, user__is_active=True, user__is_superuser=False).count(),
        "students_count": Student.objects.filter(school=s, active=True).count(),
        "roles": [
            {"id": str(r.id), "code": r.code, "label": public_role_label(r, s),
             "suggested_function": suggested_account_function(s, r.code, functions)}
            for r in roles if role_available(s, r.code)
        ],
        "members": [
            {
                "id": str(m.pk), "username": m.user.schoollogin_set.filter(school=m.school).values_list("username", flat=True).first() or m.user.username,
                "name": f"{m.user.first_name} {m.user.last_name}".strip() or m.user.username,
                "email": m.user.email, "active": m.active and m.user.is_active,
                "membership_active": m.active, "role_id": str(m.role_id),
                "role": public_role_label(m.role, s), "role_code": m.role.code,
                "is_platform_admin": m.user.is_superuser,
            } for m in members[:250]
        ],
        "members_truncated": members.count() > 250,
        "policy": {
            "plan_name": policy.plan_name if policy else "Sans formule",
            "max_users": policy.max_users if policy else None,
            "max_students": policy.max_students if policy else None,
            "revision": policy.revision if policy else 0,
        },
        "events": recent_events(20, str(s.pk)),
    }


@require_GET
@authorized
def platform_school_detail(request, school_id):
    if not platform_only(request):
        return denied()
    school = School.objects.select_related("organization").filter(pk=school_id).first()
    if school is None:
        return JsonResponse({"error": "Établissement introuvable."}, status=404)
    return JsonResponse(detail_dict(school))


def validate_reason(body):
    reason = body.get("reason")
    if not string(reason, 240):
        return None
    return reason.strip()


@require_http_methods(["POST"])
@authorized
def platform_school_action(request, school_id):
    if not platform_only(request):
        return denied()
    body, error = parse_body(request)
    if error is not None:
        return error
    reason = validate_reason(body)
    if not reason:
        return JsonResponse({"error": "Le motif de modification est obligatoire."}, status=422)
    action = body.get("action")
    with transaction.atomic():
        school = School.objects.select_for_update().select_related("organization").filter(pk=school_id).first()
        if school is None:
            return JsonResponse({"error": "Établissement introuvable."}, status=404)
        if action == "status":
            if type(body.get("active")) is not bool:
                return JsonResponse({"error": "État de l'établissement invalide."}, status=422)
            if school.is_active == body["active"]:
                return JsonResponse({"error": "Cet établissement possède déjà cet état."}, status=409)
            school.is_active = body["active"]
            school.save(update_fields=["is_active"])
            event = "school_reactivated" if school.is_active else "school_suspended"
            log_event(school, request, event, reason)
            audit(request, event, school.name, school, reason)
        elif action == "rename":
            name = body.get("name")
            if not string(name, 180):
                return JsonResponse({"error": "Nom d'établissement invalide."}, status=422)
            name = name.strip()
            school.name = name
            school.save(update_fields=["name"])
            audit(request, "school_renamed", name, school, reason)
        elif action == "profile":
            try:
                school_type, education_cycles = validate_school_profile(
                    body.get("school_type"), body.get("education_cycles")
                )
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=422)
            if school.school_type == school_type and school.education_cycles == education_cycles:
                return JsonResponse({"error": "La classification est déjà à jour."}, status=409)
            # Ne jamais modifier ou supprimer les cycles/classes réels :
            # il s’agit ici d’une classification administrative distincte.
            school.school_type = school_type
            school.education_cycles = education_cycles
            school.save(update_fields=["school_type", "education_cycles"])
            provision_appointment_roles(school)
            log_event(school, request, "school_profile_updated", reason)
            audit(request, "school_profile_updated", school.name, school, reason)
        elif action == "plan":
            label = body.get("plan_name")
            revision = body.get("revision")
            if not string(label, 80) or type(revision) is not int or revision < 0:
                return JsonResponse({"error": "Formule ou révision invalide."}, status=422)
            caps = {}
            for key in ("max_users", "max_students"):
                value = body.get(key)
                if value is not None and (type(value) is not int or not 1 <= value <= 1000000):
                    return JsonResponse({"error": "Un plafond doit être un entier positif ou vide."}, status=422)
                caps[key] = value
            policy = SchoolAdminPolicy.objects.select_for_update().filter(school=school).first()
            current_revision = policy.revision if policy else 0
            if current_revision != revision:
                return JsonResponse({"error": "Les paramètres ont changé. Rechargez la fiche.", "revision": current_revision}, status=409)
            if policy is None:
                policy = SchoolAdminPolicy(school=school)
            policy.plan_name = label.strip()
            policy.max_users = caps["max_users"]
            policy.max_students = caps["max_students"]
            policy.revision += 1
            policy.save()
            audit(request, "limits_updated", school.name, school, reason)
        else:
            return JsonResponse({"error": "Action non reconnue."}, status=422)
    return JsonResponse(detail_dict(school))


@require_http_methods(["POST"])
@authorized
def platform_member_action(request, school_id, member_id):
    if not platform_only(request):
        return denied()
    body, error = parse_body(request)
    if error is not None:
        return error
    reason = validate_reason(body)
    if not reason:
        return JsonResponse({"error": "Un motif est obligatoire."}, status=422)
    with transaction.atomic():
        school = School.objects.select_for_update().filter(pk=school_id).first()
        if school is None:
            return JsonResponse({"error": "Établissement introuvable."}, status=404)
        member = SchoolMember.objects.select_for_update().select_related("user", "role").filter(
            school=school, pk=member_id
        ).first()
        if member is None:
            return JsonResponse({"error": "Compte introuvable dans cet établissement."}, status=404)
        if member.user_id == request.user.pk or member.user.is_superuser:
            return JsonResponse({"error": "Les comptes de plateforme ne se modifient pas ici."}, status=403)
        action = body.get("action")
        if action == "role":
            try:
                valid_role_id = UUID(str(body.get("role_id")))
            except (ValueError, TypeError, AttributeError):
                return JsonResponse({"error": "Identifiant de rôle invalide."}, status=422)
            role = SchoolRole.objects.filter(school=school, pk=valid_role_id).first()
            if role is None or not role_available(school, role.code):
                return JsonResponse({"error": "Rôle inconnu pour cet établissement."}, status=422)
            member.role = role
            member.is_school_owner = role.code == OWNER_ROLE_CODE
            if member.is_school_owner:
                member.access_cycle_ids = None
            member.save(update_fields=["role", "is_school_owner", "access_cycle_ids"])
            event = "member_role_changed"
        elif action == "status":
            if type(body.get("active")) is not bool:
                return JsonResponse({"error": "État du membre invalide."}, status=422)
            active = body["active"]
            if member.active == active:
                return JsonResponse({"error": "Ce compte possède déjà cet état."}, status=409)
            policy = SchoolAdminPolicy.objects.select_for_update().filter(school=school).first()
            if active and policy and policy.max_users is not None and (
                SchoolMember.objects.filter(school=school, active=True, user__is_active=True, user__is_superuser=False).count() >= policy.max_users
            ):
                return JsonResponse({"error": "Plafond de comptes atteint."}, status=409)
            member.active = active
            member.save(update_fields=["active"])
            event = "member_reactivated" if active else "member_suspended"
        else:
            return JsonResponse({"error": "Action inconnue."}, status=422)
        log_event(school, request, event, str(member.user.pk))
        audit(request, event, f"{member.user.username} · {school.name}", school, reason)
    return JsonResponse(detail_dict(school))


@require_GET
@authorized
def platform_audit(request):
    if not platform_only(request):
        return denied()
    school_id = request.GET.get("school_id") or None
    if school_id:
        try:
            school_id = UUID(str(school_id))
        except (ValueError, TypeError, AttributeError):
            return JsonResponse({"error": "Identifiant d'établissement invalide."}, status=422)
        if not School.objects.filter(pk=school_id).exists():
            return JsonResponse({"error": "Établissement introuvable."}, status=404)
    limit = size(request.GET.get("limit"), default=50, upper=100)
    return JsonResponse({"events": recent_events(limit, school_id)})


@require_GET
@authorized
def platform_school_members(request, school_id):
    """Paginated, searchable school-scoped member directory for the platform."""
    if not platform_only(request):
        return denied()
    school = School.objects.filter(pk=school_id).first()
    if school is None:
        return JsonResponse({"error": "Établissement introuvable."}, status=404)
    search = str(request.GET.get("q", "")).strip()[:80]
    page = size(request.GET.get("page"), 1)
    per_page = size(request.GET.get("per_page"), 20, 50)
    qs = SchoolMember.objects.filter(school=school).select_related("user", "role")
    if search:
        qs = qs.filter(
            Q(user__username__icontains=search) | Q(user__schoollogin__school=school, user__schoollogin__username__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__email__icontains=search)
            | Q(role__label__icontains=search)
        )
    total = qs.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    rows = qs.order_by("user__last_name", "user__username")[(page - 1) * per_page:page * per_page]
    return JsonResponse({
        "members": [
            {
                "id": str(m.id), "username": m.user.schoollogin_set.filter(school=m.school).values_list("username", flat=True).first() or m.user.username,
                "name": f"{m.user.first_name} {m.user.last_name}".strip() or m.user.username,
                "email": m.user.email, "active": m.active and m.user.is_active,
                "membership_active": m.active,
                "role_id": str(m.role_id), "role": public_role_label(m.role, school), "role_code": m.role.code,
                "is_platform_admin": m.user.is_superuser,
            } for m in rows
        ],
        "total": total, "page": page, "pages": pages, "per_page": per_page,
    })
