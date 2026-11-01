from django.urls import path
from pedagogy import views

urlpatterns = [
    path("", views.index),
    path("healthz", views.health),
    path("readyz", views.ready),
    path("api/v1/presets", views.preset_list),
    path("api/v1/policies/validate", views.validate),
    path("api/v1/evaluate", views.simulate),
]
