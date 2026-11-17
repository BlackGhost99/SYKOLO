"""Shared visibility rules for the parent catalogue and admissions."""
from django.db.models import Q

from .academic_models import AcademicClass


def active_classrooms():
    return AcademicClass.objects.filter(
        active=True, school__is_active=True, year__active=True,
        level__active=True, level__cycle__active=True,
    ).filter(Q(track__isnull=True) | Q(track__active=True))


def public_classrooms():
    # Legacy unpublished listing rows must not hide configured active schools.
    return active_classrooms()
