"""Institution-scoped permission and configuration resolution."""
import copy
import json
import re
from itertools import combinations

from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse

from .models import OrganizationMember, School, SchoolMember, SchoolSetting, SchoolAdminPolicy, Student, PermissionDelegation, SchoolRole

PERMISSIONS = frozenset({
    "school.view", "school.members.read", "school.members.write",
    "school.roles.read", "school.roles.manage",
    "school.settings.read", "school.settings.write", "school.audit.read",
    "school.academic.read", "school.academic.manage", "school.classes.manage",
    "school.admissions.read", "school.admissions.manage", "school.admissions.decide", "school.admissions.enroll",
    "school.parents.manage",
    "school.students.read", "school.students.manage",
    "school.staff.read", "school.staff.manage",
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

# Initial editable role templates, not institution-wide immutable business rules.
ROLE_TEMPLATES = [
    ("direction", "Directeur / Directrice", sorted(PERMISSIONS - {"school.finance.receive", "school.finance.reverse", "school.finance.manage", "school.finance.deposit"})),
    ("secretariat", "Secrétariat", ["school.view", "school.members.read", "school.settings.read", "school.academic.read", "school.students.read", "school.students.manage", "school.admissions.read", "school.admissions.manage", "school.admissions.enroll", "school.staff.read", "school.staff.manage", "school.organization.read", "school.curriculum.read", "school.curriculum.manage", "school.reports.read", "school.deliberations.read", "school.attendance.read", "school.attendance.write", "school.timetable.read", "school.timetable.manage"]),
    ("enseignant", "Enseignant", ["school.view", "school.settings.read", "school.academic.read", "school.curriculum.read", "school.timetable.read"]),
    ("comptabilite", "Comptabilité", ["school.view", "school.students.read", "school.academic.read", "school.finance.read", "school.finance.approve", "school.finance.reverse"]),
    ("econome", "Économe / Caissier", ["school.view", "school.students.read", "school.academic.read", "school.finance.read", "school.finance.receive", "school.finance.deposit"]),
    ("tarification", "Responsable des tarifs", ["school.view", "school.finance.read", "school.finance.manage"]),
    ("parent", "Parent", ["school.view"]),
    ("eleve", "Élève", ["school.view"]),
]

PROFILE_ROLE_LABELS = {
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
SECONDARY_ROLE_TEMPLATES = {
    "college": (
        ("etudes", "Direction des études", SECONDARY_STUDIES_PERMISSIONS),
        ("vie_scolaire", "Surveillant général / Conseiller d’éducation", (
            *SECONDARY_ATTENDANCE_PERMISSIONS, "school.attendance.finalize",
        )),
        SECONDARY_SURVEILLANCE,
    ),
    "lycee_general": (
        ("etudes", "Censeur pédagogique / Direction des études", SECONDARY_STUDIES_PERMISSIONS),
        ("vie_scolaire", "Censeur de la vie scolaire", (
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


def role_templates_for(school):
    labels = PROFILE_ROLE_LABELS.get(school.school_type, {})
    return [
        (code, labels.get(code, label), list(permissions))
        for code, label, permissions in (*ROLE_TEMPLATES, *SECONDARY_ROLE_TEMPLATES.get(school.school_type, ()))
        if code != "eleve" or school.school_type != "maternelle"
    ]


def provision_secondary_roles(school):
    SchoolRole.objects.bulk_create([
        SchoolRole(school=school, code=code, label=label, permissions=list(permissions))
        for code, label, permissions in SECONDARY_ROLE_TEMPLATES.get(school.school_type, ())
    ], ignore_conflicts=True)


SCOPE_FIELDS = ("year", "cycle", "level", "class")


def public_role_label(role, school=None):
    """Use the inclusive title for legacy built-in roles, retain school custom labels."""
    school_type = (school or role.school).school_type
    for code, label, _ in SECONDARY_ROLE_TEMPLATES.get(school_type, ()):
        if role.code == code and any(
            role.label == old_label
            for templates in SECONDARY_ROLE_TEMPLATES.values()
            for old_code, old_label, _ in templates
            if old_code == code
        ):
            return label
    labels = PROFILE_ROLE_LABELS.get(school_type, {})
    if role.code in labels:
        default_labels = {label for code, label, _ in ROLE_TEMPLATES if code == role.code}
        if role.label in default_labels or (role.code == "direction" and role.label == "Direction"):
            return labels[role.code]
    if role.code == "direction" and role.label == "Direction":
        return "Directeur / Directrice"
    return role.label


def owns_organization(user, organization):
    return OrganizationMember.objects.filter(organization=organization, user=user, role="founder").exists()


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
