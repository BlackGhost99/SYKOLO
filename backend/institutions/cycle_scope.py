"""Périmètre des comptes scolaires : UUID de cycles académiques réels.

None = historique / accès à l'établissement entier.
Liste non vide = accès limité aux cycles explicitement désignés.
Toute API non auditée pour ce périmètre doit refuser ces comptes (middleware).
"""
from uuid import UUID

from .academic_models import AcademicCycle
from .models import SchoolMember, OrganizationMember


def scoped_cycle_ids(user, school):
    """None si accès global ; set[str] si membre limité. Les propriétaires restent globaux."""
    if not user.is_authenticated or not user.is_active:
        return set()
    if OrganizationMember.objects.filter(
        organization=school.organization, user=user, role="founder"
    ).exists():
        return None
    member = SchoolMember.objects.filter(
        school=school, user=user, active=True, role__school=school
    ).first()
    if not member:
        return set()
    if member.access_cycle_ids is None:
        return None
    return set(member.access_cycle_ids)


def validate_cycle_scope(school, ids, *, allow_global=True):
    if ids is None:
        if not allow_global:
            raise ValueError("Sélectionnez au moins un cycle autorisé.")
        return None
    if not isinstance(ids, list) or not 1 <= len(ids) <= 20:
        raise ValueError("Sélectionnez entre 1 et 20 cycles académiques.")
    clean = []
    for v in ids:
        if not isinstance(v, str):
            raise ValueError("Identifiant de cycle invalide.")
        try:
            uid = UUID(v)
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Identifiant de cycle invalide.") from None
        clean.append(str(uid))
    if len(clean) != len(set(clean)):
        raise ValueError("Un même cycle est sélectionné plusieurs fois.")
    known = set(str(v) for v in AcademicCycle.objects.filter(
        school=school, pk__in=clean, active=True
    ).values_list("pk", flat=True))
    if known != set(clean):
        raise ValueError("Cycle académique inactif ou étranger à cet établissement.")
    return sorted(clean)


def scope_catalog(school):
    return list(AcademicCycle.objects.filter(
        school=school, active=True
    ).order_by("order", "name").values("id", "code", "name"))


def profile_cycle_keys(school, scoped_ids):
    """Ne jamais deviner une correspondance entre codes de cycles académiques et profils."""
    if scoped_ids is None:
        return set(school.education_cycles or [])
    return set(AcademicCycle.objects.filter(
        school=school, pk__in=scoped_ids, active=True,
        code__in=school.education_cycles or [],
    ).values_list("code", flat=True))


def has_cycle_scope(user, school, cycle_id):
    allowed = scoped_cycle_ids(user, school)
    return allowed is None or str(cycle_id) in allowed


def allowed_school_permissions(perms, scoped_ids):
    """Permissions UI exposées par les APIs explicitement vérifiées pour un compte limité."""
    if scoped_ids is None:
        return sorted(perms)
    allowed = {
        "school.view", "school.academic.read", "school.students.read",
        "school.staff.manage",
    }
    return sorted(set(perms) & allowed)
