from django.urls import include, path
from pedagogy import views
from pedagogy.pwa_views import pwa_asset

urlpatterns = [
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("institutions.urls")),
    path("manifest.webmanifest", pwa_asset, {"name":"manifest.webmanifest"}),
    path("service-worker.js", pwa_asset, {"name":"service-worker.js"}),
    path("offline.html", pwa_asset, {"name":"offline.html"}),
    path("icons/icon-192.png", pwa_asset, {"name":"icons/icon-192.png"}),
    path("icons/icon-512.png", pwa_asset, {"name":"icons/icon-512.png"}),
    path("", views.index),
    path("healthz", views.health),
    path("readyz", views.ready),
    path("api/v1/presets", views.preset_list),
    path("api/v1/policies/validate", views.validate),
    path("api/v1/evaluate", views.simulate),
]
