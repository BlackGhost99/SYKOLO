from django.urls import path
from . import views, parent_signup_views, password_admin_views

urlpatterns = [
    path("csrf", views.csrf),
    path("parents/registration-status", parent_signup_views.registration_status),
    path("parents/resend-verification", parent_signup_views.resend_verification),
    path("parents/register", parent_signup_views.register),
    path("parents/verify", parent_signup_views.verify),
    path("me", views.me),
    path("login", views.sign_in),
    path("logout", views.sign_out),
    path("password/change", views.change_password),
    path("password/reset/request", views.password_reset_request),
    path("password/reset/confirm", views.password_reset_confirm),
    path("password/admin-reset", password_admin_views.admin_password_reset),
    path("password/admin-parent-reset", password_admin_views.admin_parent_password_reset),
    path("mfa/begin", views.mfa_begin),
    path("mfa/confirm", views.mfa_confirm),
    path("mfa/disable", views.mfa_disable),
    path("audit", views.platform_audit),
]
