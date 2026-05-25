# accounts/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views

from .views import (
    CustomLoginView,
    CustomLogoutView,
    RegisterTemplateView,
    ProfileView,
)

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login-template"),
    path("logout/", CustomLogoutView.as_view(), name="logout-template"),
    path("register/", RegisterTemplateView.as_view(), name="register-template"),
    path("profile/", ProfileView.as_view(), name="profile"),

    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.html",
            success_url="/shop/accounts/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url="/shop/accounts/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]