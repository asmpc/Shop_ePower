from django.urls import path

from .views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    RegisterAPIView,
    LogoutAPIView,
    UserProfileAPIView,
)

urlpatterns = [
    path("login/", CustomTokenObtainPairView.as_view(), name="api-login"),
    path("refresh/", CustomTokenRefreshView.as_view(), name="api-refresh"),
    path("register/", RegisterAPIView.as_view(), name="api-register"),
    path("logout/", LogoutAPIView.as_view(), name="api-logout"),
    path("profile/", UserProfileAPIView.as_view(), name="api-profile"),
]