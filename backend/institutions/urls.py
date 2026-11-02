from django.urls import path
from . import views, academic_views, student_views

urlpatterns = [
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
