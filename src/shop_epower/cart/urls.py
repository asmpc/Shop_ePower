from django.urls import path

from .views import (
    CartDetailView,
    CartAddView,
    CartRemoveView,
    CartClearView,


)


urlpatterns = [
    path(
        "",
        CartDetailView.as_view(),
        name="cart-detail",
    ),

    path(
        "add/<uuid:product_id>/",
        CartAddView.as_view(),
        name="cart-add",
    ),

    path(
        "remove/<uuid:product_id>/",
        CartRemoveView.as_view(),
        name="cart-remove",
    ),

    path(
        "clear/",
        CartClearView.as_view(),
        name="cart-clear",
    ),

]