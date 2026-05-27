from django.urls import path

from .views import (
    CheckoutAPIView,
    OrderListAPIView,
    OrderDetailAPIView,
    OrderCancelAPIView,
)


app_name = "api_orders"


urlpatterns = [
    path("", OrderListAPIView.as_view(), name="list"),
    path("checkout/", CheckoutAPIView.as_view(), name="checkout"),
    path("<int:order_id>/", OrderDetailAPIView.as_view(), name="detail"),
    path("<int:order_id>/cancel/", OrderCancelAPIView.as_view(), name="cancel"),
]