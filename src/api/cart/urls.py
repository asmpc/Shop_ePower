from django.urls import path

from .views import (
    CartAddItemAPIView,
    CartAPIView,
    CartClearAPIView,
    CartRemoveItemAPIView,
)

urlpatterns = [
    path(
        "",
        CartAPIView.as_view(),
        name="api-cart-detail",
    ),
    path(
        "add/",
        CartAddItemAPIView.as_view(),
        name="api-cart-add",
    ),

    path(
        "remove/",
        CartRemoveItemAPIView.as_view(),
        name="api-cart-remove",
    ),

    path(
        "clear/",
        CartClearAPIView.as_view(),
        name="api-cart-clear",
    ),


]