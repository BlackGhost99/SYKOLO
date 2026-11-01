from django.urls import path
from . import views

urlpatterns = [
    path("csrf", views.csrf),
    path("me", views.me),
    path("login", views.sign_in),
    path("logout", views.sign_out),
    path("password/change", views.change_password),
    path("password/reset/request", views.password_reset_request),
    path("password/reset/confirm", views.password_reset_confirm),
    path("mfa/begin", views.mfa_begin),
    path("mfa/confirm", views.mfa_confirm),
    path("mfa/disable", views.mfa_disable),
    path("audit", views.platform_audit),
]
