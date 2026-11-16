"""Shared visibility rules for the parent catalogue and admissions."""
from django.db.models import Q

from .academic_models import AcademicClass


def active_classrooms():
    return AcademicClass.objects.filter(
        active=True, school__is_active=True, year__active=True,
        level__active=True, level__cycle__active=True,
    ).filter(Q(track__isnull=True) | Q(track__active=True))


def public_classrooms():
    return active_classrooms().filter(
        Q(school__public_listing__published=True) |
        Q(school__public_listing__isnull=True)
    )
