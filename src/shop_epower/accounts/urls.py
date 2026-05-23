from django.urls import path

from .views import (
    RegisterView,
    LogoutAPIView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
)

from .views import (
    CustomLoginView,
    CustomLogoutView,
    RegisterTemplateView,
)

from .views import ProfileView

from django.contrib.auth import views as auth_views




urlpatterns = [

    # API

    path(
        'api/login/',
        CustomTokenObtainPairView.as_view(),
        name='api-login',
    ),

    path(
        'api/refresh/',
        CustomTokenRefreshView.as_view(),
        name='api-refresh',
    ),

    path(
        'api/logout/',
        LogoutAPIView.as_view(),
        name='api-logout',
    ),

    path(
        'api/register/',
        RegisterView.as_view(),
        name='api-register',
    ),

    # Templates

    path(
        'login/',
        CustomLoginView.as_view(),
        name='login-template',
    ),

    path(
        'logout/',
        CustomLogoutView.as_view(),
        name='logout-template',
    ),

    path(
        'register/',
        RegisterTemplateView.as_view(),
        name='register-template',
    ),

    path(
        'profile/',
        ProfileView.as_view(),
        name='profile',
    ),

    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset.html'
        ),
        name='password_reset',
    ),

    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html'
        ),
        name='password_reset_done',
    ),

    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html'
        ),
        name='password_reset_confirm',
    ),

    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
]