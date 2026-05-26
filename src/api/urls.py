from django.urls import include, path



urlpatterns = [
    path("accounts/", include("api.accounts.urls")),
    path("catalog/", include("api.catalog.urls")),
    path("cart/", include("api.cart.urls")),
    path("orders/", include("api.orders.urls")),
]