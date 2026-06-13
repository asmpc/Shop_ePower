from django.urls import path
from shop_epower.payments.views import (
    mock_checkout_view,
    mock_payment_success_view,
    mock_payment_fail_view,
)


app_name = "payments"


urlpatterns = [
    path(
        "mock/<str:transaction_id>/",
        mock_checkout_view,
        name="mock_checkout",
    ),

    path(
        "mock/<str:transaction_id>/success/",
        mock_payment_success_view,
        name="mock_payment_success",
    ),

    path(
        "mock/<str:transaction_id>/fail/",
        mock_payment_fail_view,
        name="mock_payment_fail",
    ),


]