from django.urls import path
from .views import checkout_view, order_success_view

app_name = "orders"

urlpatterns = [
    path("checkout/", checkout_view, name="checkout"),
    path("success/<int:order_id>/", order_success_view, name="success"),
]