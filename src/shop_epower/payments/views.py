from django.shortcuts import get_object_or_404
from django.shortcuts import render

from shop_epower.payments.models import Payment
from django.shortcuts import redirect
from django.urls import reverse

from shop_epower.payments.services import (
    mark_payment_paid,
    mark_payment_failed,
)


def mock_checkout_view(
    request,
    transaction_id,
):
    payment = get_object_or_404(
        Payment,
        transaction_id=transaction_id,
    )

    return render(
        request,
        "payments/mock_checkout.html",
        {
            "payment": payment,
        },
    )


def mock_payment_success_view(
    request,
    transaction_id,
):
    payment = get_object_or_404(
        Payment,
        transaction_id=transaction_id,
    )

    mark_payment_paid(
        payment=payment,
        manager_comment="Mock provider payment success.",
    )

    return redirect(
        reverse(
            "orders:detail",
            args=[payment.order.id],
        )
    )


def mock_payment_fail_view(
    request,
    transaction_id,
):
    payment = get_object_or_404(
        Payment,
        transaction_id=transaction_id,
    )

    mark_payment_failed(
        payment=payment,
        manager_comment="Mock provider payment failed.",
    )

    return redirect(
        reverse(
            "orders:detail",
            args=[payment.order.id],
        )
    )