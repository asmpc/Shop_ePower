from django.urls import include, path


urlpatterns = [
    path("accounts/", include("api.accounts.urls")),
    path("catalog/", include("api.catalog.urls")),
]