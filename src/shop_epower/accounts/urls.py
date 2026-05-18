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
]