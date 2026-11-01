from django.urls import include, path
from pedagogy import views

urlpatterns = [
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("institutions.urls")),
    path("", views.index),
    path("healthz", views.health),
    path("readyz", views.ready),
    path("api/v1/presets", views.preset_list),
    path("api/v1/policies/validate", views.validate),
    path("api/v1/evaluate", views.simulate),
]
