"""Institution-scoped permission and configuration resolution."""
import copy
import json
import re
from itertools import combinations

from django.db.models import Q
from django.http import JsonResponse

from .models import OrganizationMember, School, SchoolMember, SchoolSetting, SchoolAdminPolicy, Student
from .school_profiles import TYPE_DIRECTOR_LABEL, profile_payload

PERMISSIONS = frozenset({
    "school.view", "school.members.read", "school.members.write",
    "school.roles.read", "school.roles.manage",
    "school.settings.read", "school.settings.write", "school.audit.read",
    "school.academic.read", "school.academic.manage",
    "school.admissions.read", "school.admissions.manage", "school.admissions.decide", "school.admissions.enroll",
    "school.parents.manage",
    "school.students.read", "school.students.manage",
    "school.staff.read", "school.staff.manage",
    "school.curriculum.read", "school.curriculum.manage",
    "school.assessments.read", "school.assessments.manage",
    "school.reports.read", "school.reports.manage", "school.reports.publish",
    "school.deliberations.read", "school.deliberations.manage", "school.deliberations.finalize",
    "school.reports.amend",
    "school.timetable.read", "school.timetable.manage",
    "school.attendance.read", "school.attendance.write", "school.attendance.finalize",
    "school.finance.read", "school.finance.manage", "school.finance.receive", "school.finance.reverse",
})

# Initial editable role templates, not institution-wide immutable business rules.
ROLE_TEMPLATES = [
    ("direction", "Direction", sorted(PERMISSIONS)),
    ("secretariat", "Secrétariat", ["school.view", "school.members.read", "school.settings.read", "school.academic.read", "school.students.read", "school.students.manage", "school.admissions.read", "school.admissions.manage", "school.admissions.enroll", "school.staff.read", "school.staff.manage", "school.curriculum.read", "school.curriculum.manage", "school.reports.read", "school.deliberations.read", "school.attendance.read", "school.attendance.write", "school.timetable.read", "school.timetable.manage"]),
    ("enseignant", "Enseignant", ["school.view", "school.settings.read", "school.academic.read", "school.curriculum.read", "school.timetable.read"]),
    ("comptabilite", "Comptabilité", ["school.view", "school.students.read", "school.academic.read", "school.finance.read", "school.finance.manage", "school.finance.receive"]),
    ("parent", "Parent", ["school.view"]),
    ("eleve", "Élève", ["school.view"]),
]

# Suggested roles for each school type. These permissions remain editable per school.
# Legacy 'comptabilite' permissions are preserved for compatibility; finer finance segregation is a follow-up.
_FIN_READ = ["school.view", "school.academic.read", "school.students.read", "school.finance.read"]
_STUDY_READ = ["school.view", "school.academic.read", "school.students.read",
               "school.curriculum.read", "school.timetable.read", "school.reports.read"]
_STUDY_MANAGE = _STUDY_READ + ["school.curriculum.manage", "school.assessments.read",
                              "school.assessments.manage", "school.timetable.manage"]
_LIFE_STUDENT = _STUDY_READ + ["school.attendance.read", "school.attendance.write",
                              "school.attendance.finalize"]
_CYCLE_ROLE_TEMPLATES = {
    "maternelle": [
        ("educateur_maternelle", "Éducateur / Éducatrice", _STUDY_READ + ["school.attendance.read", "school.attendance.write"]),
        ("assistant_maternelle", "Assistant(e) maternelle", ["school.view", "school.academic.read", "school.attendance.read", "school.attendance.write"]),
    ],
    "primaire": [
        ("responsable_primaire", "Responsable pédagogique primaire", _STUDY_MANAGE),
    ],
    "college": [
        ("responsable_etudes", "Responsable des études", _STUDY_MANAGE),
        ("surveillant_general", "Surveillant général", _LIFE_STUDENT),
        ("intendant", "Intendant", _FIN_READ + ["school.finance.manage"]),
    ],
    "lycee": [
        ("censeur_pedagogique", "Censeur pédagogique", _STUDY_MANAGE),
        ("censeur_vie_scolaire", "Censeur de la vie scolaire", _LIFE_STUDENT),
        ("surveillant_general", "Surveillant général", _LIFE_STUDENT),
        ("intendant", "Intendant", _FIN_READ + ["school.finance.manage"]),
        ("responsable_orientation", "Responsable de l'orientation", _STUDY_READ),
    ],
}
_COMMON_EXTRA_ROLES = [
    ("econome", "Économe / Caissier", _FIN_READ + ["school.finance.receive"]),
    ("auditeur_financier", "Auditeur financier (lecture seule)", _FIN_READ + ["school.audit.read"]),
]
_CYCLE_ORDER = ("maternelle", "primaire", "college", "lycee")


def role_templates_for_profile(school_type, enabled_cycles):
    """Only *propose* templates; an existing school's customized roles survive."""
    templates = [(code, TYPE_DIRECTOR_LABEL.get(school_type, label) if code == "direction" else label,
                  list(perms)) for code, label, perms in ROLE_TEMPLATES]
    if school_type == "a_configurer":
        return templates
    seen = {code for code, _, _ in templates}
    candidates = _COMMON_EXTRA_ROLES + [
        role for cycle in _CYCLE_ORDER if cycle in enabled_cycles
        for role in _CYCLE_ROLE_TEMPLATES[cycle]
    ]
    for code, label, permissions in candidates:
        if code not in seen:
            templates.append((code, label, sorted(set(permissions) & PERMISSIONS)))
            seen.add(code)
    return templates


SCOPE_FIELDS = ("year", "cycle", "level", "class")


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
    member = SchoolMember.objects.select_related("role").filter(
        school=school, user=user, active=True, role__school=school
    ).first()
    return bool(member and permission in member.role.permissions)


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
        "id": str(school.pk), "organization_id": str(school.organization_id),
        "name": school.name, "short_name": school.short_name,
        "primary_color": school.primary_color,
        **profile_payload(school),
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
