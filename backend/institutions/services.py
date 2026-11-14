"""Institution-scoped permission and configuration resolution."""
import copy
import json
import re
from itertools import combinations

from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse

from .models import OrganizationMember, School, SchoolMember, SchoolSetting, SchoolAdminPolicy, Student, PermissionDelegation, SchoolRole
from .school_governance import GOVERNANCE_ROLE_TEMPLATES, governance_mode_for, governance_profile, governance_role_templates

PERMISSIONS = frozenset({
    "school.view", "school.members.read", "school.members.write",
    "school.roles.read", "school.roles.manage",
    "school.settings.read", "school.settings.write", "school.audit.read",
    "school.academic.read", "school.academic.manage", "school.classes.manage",
    "school.admissions.read", "school.admissions.manage", "school.admissions.decide", "school.admissions.enroll",
    "school.parents.manage",
    "school.students.read", "school.students.manage",
    "school.students.profile.read", "school.students.admin.write",
    "school.students.sensitive.read", "school.students.finance.read",
    "school.staff.read", "school.staff.manage",
    "school.staff.dossier.read", "school.staff.dossier.manage",
    "school.payroll.read", "school.payroll.manage", "school.payroll.approve", "school.payroll.pay", "school.payroll.reverse",
    "school.operating.read", "school.operating.manage", "school.operating.approve", "school.operating.pay", "school.operating.reverse",
    "school.organization.read", "school.organization.manage",
    "school.curriculum.read", "school.curriculum.manage",
    "school.assessments.read", "school.assessments.manage",
    "school.reports.read", "school.reports.manage", "school.reports.publish",
    "school.deliberations.read", "school.deliberations.manage", "school.deliberations.finalize",
    "school.reports.amend",
    "school.timetable.read", "school.timetable.manage",
    "school.attendance.read", "school.attendance.write", "school.attendance.finalize", "school.attendance.assigned",
    "school.finance.read", "school.finance.manage", "school.finance.receive", "school.finance.reverse", "school.finance.approve", "school.finance.deposit",
})

FINANCE_MUTATION_PERMISSIONS = frozenset({
    "school.finance.manage", "school.finance.receive", "school.finance.reverse",
    "school.finance.approve", "school.finance.deposit",
    "school.payroll.manage", "school.payroll.approve", "school.payroll.pay", "school.payroll.reverse",
    "school.operating.manage", "school.operating.approve", "school.operating.pay", "school.operating.reverse",
})

DIRECTION_PERMISSIONS = sorted(PERMISSIONS - {
    "school.finance.receive", "school.finance.reverse", "school.finance.manage", "school.finance.deposit",
    "school.payroll.manage", "school.payroll.pay", "school.payroll.reverse",
    "school.operating.manage", "school.operating.pay", "school.operating.reverse",
})
OWNER_ROLE_CODE = "proprietaire"
OWNER_ROLE_TEMPLATE = (OWNER_ROLE_CODE, "Propriétaire de l’établissement", (
    "school.view", "school.members.read", "school.members.write", "school.roles.read", "school.roles.manage",
    "school.audit.read",
))

# Initial editable role templates, not institution-wide immutable business rules.
ROLE_TEMPLATES = [
    ("direction", "Directeur / Directrice", DIRECTION_PERMISSIONS),
    ("secretariat", "Secrétariat", ["school.view", "school.members.read", "school.settings.read", "school.academic.read", "school.students.read", "school.students.manage", "school.students.profile.read", "school.students.admin.write", "school.students.sensitive.read", "school.admissions.read", "school.admissions.manage", "school.admissions.enroll", "school.staff.read", "school.staff.manage", "school.staff.dossier.read", "school.organization.read", "school.curriculum.read", "school.curriculum.manage", "school.reports.read", "school.deliberations.read", "school.attendance.read", "school.attendance.write", "school.timetable.read", "school.timetable.manage"]),
    ("enseignant", "Enseignant", ["school.view", "school.settings.read", "school.academic.read", "school.curriculum.read", "school.timetable.read"]),
    ("comptabilite", "Comptabilité", ["school.view", "school.students.finance.read", "school.academic.read", "school.finance.read", "school.finance.approve", "school.finance.reverse",
        "school.payroll.read", "school.payroll.manage", "school.payroll.reverse",
        "school.operating.read", "school.operating.manage", "school.operating.reverse"]),
    ("econome", "Économe / Caissier", ["school.view", "school.students.finance.read", "school.academic.read", "school.finance.read", "school.finance.receive", "school.finance.deposit",
        "school.payroll.read", "school.payroll.pay", "school.operating.read", "school.operating.pay"]),
    ("tarification", "Responsable des tarifs", ["school.view", "school.finance.read", "school.finance.manage"]),
    ("parent", "Parent", ["school.view"]),
    ("eleve", "Élève", ["school.view"]),
]

PROFILE_ROLE_LABELS = {
    "groupe_scolaire": {"direction": "Direction générale"},
    "college": {"direction": "Principal / Principale du collège", "enseignant": "Professeur / Professeure du collège"},
    "lycee_general": {"direction": "Proviseur / Proviseure du lycée", "enseignant": "Professeur / Professeure du lycée"},
    "lycee_technique": {"direction": "Proviseur / Proviseure du lycée technique", "enseignant": "Professeur / Professeure du lycée technique"},
    "maternelle": {
        "direction": "Direction de la maternelle",
        "enseignant": "Éducateur / Éducatrice de maternelle",
        "secretariat": "Secrétariat de la maternelle",
        "econome": "Caisse / Économat",
    },
    "primaire": {
        "direction": "Direction du primaire",
        "enseignant": "Enseignant / Enseignante du primaire",
        "secretariat": "Secrétariat du primaire",
        "econome": "Caisse / Économat",
    },
}


SECONDARY_STUDIES_PERMISSIONS = (
    "school.view", "school.academic.read", "school.curriculum.read", "school.curriculum.manage",
    "school.staff.read", "school.timetable.read", "school.timetable.manage",
    "school.assessments.read", "school.reports.read", "school.deliberations.read",
)
SECONDARY_ATTENDANCE_PERMISSIONS = (
    "school.view", "school.academic.read", "school.attendance.read", "school.attendance.write",
)
SECONDARY_SURVEILLANCE = ("surveillance", "Surveillance", (
    "school.view", "school.academic.read", "school.attendance.assigned",
))
SECONDARY_LYCEE_ROLES = (
    ("censeur_principal", "Censeur principal", (*SECONDARY_STUDIES_PERMISSIONS, "school.attendance.read")),
    ("surveillance_generale", "Surveillance générale", SECONDARY_ATTENDANCE_PERMISSIONS),
    SECONDARY_SURVEILLANCE,
)
SECONDARY_SECRETARIAT = ("secretariat_pedagogique", "Secrétaire pédagogique", (
    "school.view", "school.academic.read", "school.students.read", "school.students.profile.read", "school.curriculum.read",
    "school.timetable.read", "school.assessments.read", "school.reports.read",
))
SECONDARY_ROLE_TEMPLATES = {
    "college": (
        ("etudes", "Direction des études / Chargé des études", SECONDARY_STUDIES_PERMISSIONS),
        ("vie_scolaire", "Direction de la vie scolaire", (
            *SECONDARY_ATTENDANCE_PERMISSIONS, "school.attendance.finalize",
        )),
        ("surveillance_generale", "Surveillant général / Conseiller d’éducation", SECONDARY_ATTENDANCE_PERMISSIONS),
        SECONDARY_SURVEILLANCE,
    ),
    "lycee_general": (
        ("etudes", "Censeur pédagogique / Direction des études", SECONDARY_STUDIES_PERMISSIONS),
        ("vie_scolaire", "Censeur / Direction de la vie scolaire", (
            *SECONDARY_ATTENDANCE_PERMISSIONS, "school.attendance.finalize",
        )),
        *SECONDARY_LYCEE_ROLES,
    ),
    "lycee_technique": (
        ("etudes", "Direction des études du lycée technique", SECONDARY_STUDIES_PERMISSIONS),
        ("vie_scolaire", "Direction de la vie scolaire", (
            *SECONDARY_ATTENDANCE_PERMISSIONS, "school.attendance.finalize",
        )),
        *SECONDARY_LYCEE_ROLES,
        ("chef_travaux", "Chef de travaux", (
            "school.view", "school.academic.read", "school.curriculum.read",
        )),
    ),
}
SECONDARY_HEAD_CODES = {"college": "principal", "lycee_general": "proviseur", "lycee_technique": "proviseur"}
SECONDARY_CODES = {code for templates in SECONDARY_ROLE_TEMPLATES.values() for code, _, _ in templates} | {
    *SECONDARY_HEAD_CODES.values(), SECONDARY_SECRETARIAT[0],
}


def appointment_role_templates(school):
    public = governance_mode_for(school) == "public"
    roles = {} if public else {OWNER_ROLE_CODE: OWNER_ROLE_TEMPLATE}
    cycles = school.education_cycles or [school.school_type]
    for profile, templates in SECONDARY_ROLE_TEMPLATES.items():
        if profile not in cycles:
            continue
        head = SECONDARY_HEAD_CODES[profile]
        head_perms = [p for p in DIRECTION_PERMISSIONS if not (public and p in FINANCE_MUTATION_PERMISSIONS)]
        roles[head] = (head, PROFILE_ROLE_LABELS[profile]["direction"], head_perms)
        roles.update({row[0]: row for row in (*templates, SECONDARY_SECRETARIAT)})
    return roles


def role_templates_for(school):
    labels = PROFILE_ROLE_LABELS.get(school.school_type, {})
    public = governance_mode_for(school) == "public"
    return [
        (code, labels.get(code, label),
         [p for p in permissions if not (public and p in FINANCE_MUTATION_PERMISSIONS)])
        for code, label, permissions in (*ROLE_TEMPLATES, *appointment_role_templates(school).values(), *governance_role_templates(school))
        if (code != "eleve" or school.school_type != "maternelle")
        and (not public or code not in {OWNER_ROLE_CODE, "tarification"})
    ]


def provision_appointment_roles(school):
    SchoolRole.objects.bulk_create([
        SchoolRole(school=school, code=code, label=label, permissions=list(permissions))
        for code, label, permissions in (*appointment_role_templates(school).values(), *governance_role_templates(school))
    ], ignore_conflicts=True)


def role_available(school, code):
    if code == OWNER_ROLE_CODE and governance_mode_for(school) == "public":
        return False
    if code in {item[0] for group in GOVERNANCE_ROLE_TEMPLATES.values() for item in group}:
        return code in {role[0] for role in governance_role_templates(school)}
    return code not in SECONDARY_CODES or code in appointment_role_templates(school)


SCOPE_FIELDS = ("year", "cycle", "level", "class")


def public_role_label(role, school=None):
    """Use the inclusive title for legacy built-in roles, retain school custom labels."""
    school = school or role.school
    base = next((label for code, label, _ in ROLE_TEMPLATES if code == role.code), None)
    if base:
        known = {labels.get(role.code) for labels in PROFILE_ROLE_LABELS.values()} | {base}
        if role.code == "direction":
            known.add("Direction")
        if role.label in known:
            return PROFILE_ROLE_LABELS.get(school.school_type, {}).get(role.code, base)
    template = appointment_role_templates(school).get(role.code)
    if template:
        known = {label for roles in SECONDARY_ROLE_TEMPLATES.values() for code, label, _ in roles if code == role.code}
        known.update({
            "proprietaire": {"Propriétaire"},
            "principal": {PROFILE_ROLE_LABELS["college"]["direction"]},
            "proviseur": {PROFILE_ROLE_LABELS[k]["direction"] for k in ("lycee_general", "lycee_technique")},
            "etudes": {"Direction des études"},
            "vie_scolaire": {"Surveillant général / Conseiller d’éducation", "Censeur de la vie scolaire"},
        }.get(role.code, ()))
        if role.label in known:
            return template[1]
    return role.label


def owns_organization(user, organization):
    return OrganizationMember.objects.filter(organization=organization, user=user, role="founder").exists()


def owns_school(user, school):
    return owns_organization(user, school.organization) or SchoolMember.objects.filter(
        school=school, user=user, active=True, is_school_owner=True,
        role__school=school, role__code=OWNER_ROLE_CODE,
    ).exists()


def platform_only(request):
    return bool(request.user.is_superuser and request.session.get("mfa_verified", False))


def school_access(user, school_id):
    if not user.is_authenticated or not user.is_active:
        return None
    return School.objects.filter(
        Q(organization__members__user=user, organization__members__role="founder")
        | Q(members__user=user, members__active=True),
        pk=school_id, is_active=True,
    ).distinct().first()


def has_permission(user, school, permission):
    if permission == "school.members.write" and owns_organization(user, school.organization):
        # A founder can appoint a director but is not automatically that director.
        return True
    return permission in effective_permissions(user, school)


def class_management_scope(user, school):
    """None means all cycles; a set contains explicitly delegated academic cycle codes."""
    if effective_permissions(user, school) & {"school.academic.manage", "school.classes.manage"}:
        return None
    grants = PermissionDelegation.objects.filter(
        school=school, member__school=school, member__role__school=school, member__user=user,
        member__active=True, revoked_at__isnull=True,
    ).exclude(class_cycle="").filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    return {grant.class_cycle for grant in grants if "school.classes.manage" in grant.permissions}


def can_manage_classes(user, school, cycle=None):
    scope = class_management_scope(user, school)
    return scope is None or (cycle in scope if cycle is not None else bool(scope))


def effective_permissions(user, school):
    member = SchoolMember.objects.select_related("role").prefetch_related("additional_roles").filter(
        school=school, user=user, active=True, role__school=school
    ).first()
    founder_permissions = {"school.members.write"} if owns_organization(user, school.organization) else set()
    if not member:
        return founder_permissions
    roles = [member.role, *member.additional_roles.filter(school=school)]
    delegated = member.delegations.filter(school=school, revoked_at__isnull=True, class_cycle="").filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    )
    return founder_permissions | set().union(*(set(role.permissions) for role in roles),
                                             *(set(d.permissions) for d in delegated))



def quota_reached(school, resource):
    """Used within a transaction locking the school row for serial capacity checks."""
    policy = SchoolAdminPolicy.objects.filter(school=school).first()
    if not policy:
        return False
    if resource == "users" and policy.max_users is not None:
        return SchoolMember.objects.filter(school=school, active=True, user__is_active=True, user__is_superuser=False).count() >= policy.max_users
    if resource == "students" and policy.max_students is not None:
        return Student.objects.filter(school=school, active=True).count() >= policy.max_students
    return False


def school_response(school):
    return {
        "login_code": str(school.pk), "id": str(school.pk), "organization_id": str(school.organization_id),
        "name": school.name, "short_name": school.short_name,
        "primary_color": school.primary_color,
        "school_type": school.school_type,
        "school_type_label": school.get_school_type_display(),
        "education_cycles": school.education_cycles,
        "governance_mode": governance_mode_for(school),
        "governance": governance_profile(school),
    }


def validate_scope(scope):
    if not isinstance(scope, dict) or set(scope) - set(SCOPE_FIELDS):
        raise ValueError("Portée invalide.")
    clean = {}
    for k in SCOPE_FIELDS:
        if k in scope:
            v = scope[k]
            if not isinstance(v, str) or not re.fullmatch(r"[\w .-]{1,40}", v.strip()):
                raise ValueError(f"Identifiant de portée invalide : {k}.")
            clean[k] = v.strip()
    if "class" in clean and "level" not in clean:
        raise ValueError("Une classe exige un niveau.")
    if "level" in clean and "cycle" not in clean:
        raise ValueError("Un niveau exige un cycle.")
    return clean


def key_for_scope(scope):
    return json.dumps(scope, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def merge_values(left, right):
    output = copy.deepcopy(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(output.get(key), dict):
            output[key] = merge_values(output[key], value)
        else:
            output[key] = copy.deepcopy(value)
    return output


def resolve_settings(school, context, replacement=None):
    """Specific, valid school/year/cycle/level/class overrides win over general ones."""
    relevant = []
    rows = list(SchoolSetting.objects.filter(school=school))
    for row in rows:
        if all(context.get(k) == v for k, v in row.scope.items()):
            if replacement and row.scope_key == replacement[0]:
                continue
            relevant.append((row.scope, row.values, row.revision))
    if replacement:
        relevant.append((replacement[1], replacement[2], replacement[3]))
    def order(entry):
        scope = entry[0]
        return (len(scope), tuple(int(k in scope) for k in SCOPE_FIELDS))
    relevant.sort(key=order)
    effective = {}
    for scope, values, revision in relevant:
        effective = merge_values(effective, values)
    return effective, [
        {"scope": scope, "revision": revision} for scope, _, revision in relevant
    ]
