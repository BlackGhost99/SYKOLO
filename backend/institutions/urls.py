from django.urls import path
from . import views, academic_views

urlpatterns = [
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
