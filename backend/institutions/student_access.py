"""Droits distincts pour les dossiers élèves.

Les anciens droits school.students.read/manage restent reconnus pour la lecture
scolaire / les anciennes opérations de gestion, mais NE donnent pas accès aux
pièces, contacts et informations sensibles sans habilitation explicite.
"""
from .services import has_permission


STUDENT_PROFILE_READ = "school.students.profile.read"
STUDENT_ADMIN_WRITE = "school.students.admin.write"
STUDENT_SENSITIVE_READ = "school.students.sensitive.read"
STUDENT_FINANCE_READ = "school.students.finance.read"


def can_read_profile(user, school):
    return any(has_permission(user, school, code) for code in (
        STUDENT_PROFILE_READ, "school.students.read", "school.students.manage",
    ))


def can_edit_administration(user, school):
    return any(has_permission(user, school, code) for code in (
        STUDENT_ADMIN_WRITE, "school.students.manage",
    ))


def can_read_sensitive(user, school):
    return can_read_profile(user, school) and has_permission(user, school, STUDENT_SENSITIVE_READ)


def can_read_finance(user, school):
    return (has_permission(user, school, STUDENT_FINANCE_READ)
            and has_permission(user, school, "school.finance.read"))
