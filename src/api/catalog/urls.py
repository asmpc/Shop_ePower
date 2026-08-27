from django.urls import path

from .views import (
    ProductDetailAPIView,
    ProductListAPIView,
)

urlpatterns = [
    path(
        "products/",
        ProductListAPIView.as_view(),
        name="api-product-list",
    ),
    path(
        "products/<slug:slug>/",
        ProductDetailAPIView.as_view(),
        name="api-product-detail",
    ),
]