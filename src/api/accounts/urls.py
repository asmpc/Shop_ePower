from django.urls import path

from api.accounts.views import (
    CustomerAccountBalanceListAPIView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutAPIView,
    RegisterAPIView,
    UserProfileAPIView,
)

urlpatterns = [
    path("login/", CustomTokenObtainPairView.as_view(), name="api-login"),
    path("refresh/", CustomTokenRefreshView.as_view(), name="api-refresh"),
    path("register/", RegisterAPIView.as_view(), name="api-register"),
    path("logout/", LogoutAPIView.as_view(), name="api-logout"),
    path("profile/", UserProfileAPIView.as_view(), name="api-profile"),
    path(
        "balances/",
        CustomerAccountBalanceListAPIView.as_view(),
        name="api-account-balances",
    ),
]