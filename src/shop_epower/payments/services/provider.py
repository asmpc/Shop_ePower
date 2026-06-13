from django.urls import reverse

from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)


def can_create_mock_payment_url(
    *,
    payment,
):
    return (
        payment.method == PaymentMethod.ONLINE
        and payment.provider == PaymentProvider.MOCK
        and payment.status == PaymentStatus.PENDING
    )


def create_mock_payment_url(
    *,
    payment,
):
    if not can_create_mock_payment_url(
        payment=payment,
    ):
        return None

    return reverse(
        "payments:mock_checkout",
        args=[payment.transaction_id],
    )