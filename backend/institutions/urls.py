from django.urls import path
from . import views, academic_views, student_views, staff_views

urlpatterns = [
    path("schools/<uuid:school_id>/staff", staff_views.staff),
    path("schools/<uuid:school_id>/staff/me/assignments", staff_views.my_assignments),
    path("schools/<uuid:school_id>/staff/<uuid:staff_id>", staff_views.staff_detail),
    path("schools/<uuid:school_id>/staff-assignments", staff_views.assignments),
    path("schools/<uuid:school_id>/staff-assignments/<uuid:assignment_id>", staff_views.assignment_detail),
    path("schools/<uuid:school_id>/students", student_views.students),
    path("schools/<uuid:school_id>/students/<uuid:student_id>", student_views.student_detail),
    path("schools/<uuid:school_id>/students/<uuid:student_id>/guardians", student_views.guardians),
    path("schools/<uuid:school_id>/students/<uuid:student_id>/guardians/<uuid:guardian_id>", student_views.guardian_detail),
    path("schools/<uuid:school_id>/enrollments", student_views.enrollments),
    path("schools/<uuid:school_id>/enrollments/<uuid:enrollment_id>", student_views.enrollment_detail),
    path("schools/<uuid:school_id>/enrollments/<uuid:enrollment_id>/history", student_views.enrollment_history),
    path("schools/<uuid:school_id>/academic/<str:resource>", academic_views.collection),
    path("schools/<uuid:school_id>/academic/<str:resource>/<uuid:object_id>", academic_views.detail),
    path("organizations", views.organizations),
    path("organizations/<uuid:organization_id>/schools", views.organization_schools),
    path("schools", views.schools),
    path("schools/<uuid:school_id>", views.school_detail),
    path("schools/<uuid:school_id>/members", views.school_members),
    path("schools/<uuid:school_id>/roles", views.school_roles),
    path("schools/<uuid:school_id>/roles/<uuid:role_id>", views.school_role_detail),
    path("schools/<uuid:school_id>/settings", views.school_settings),
    path("schools/<uuid:school_id>/audit", views.school_audit),
]
