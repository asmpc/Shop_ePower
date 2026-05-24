from django.urls import include, path

urlpatterns = [
    path("accounts/", include("shop_epower.api.accounts.urls")),
]