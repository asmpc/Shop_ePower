from django.core.exceptions import ValidationError

from shop_epower.orders.models import DeliveryMethod
from shop_epower.payments.models import (
    PaymentMethod,
)


def validate_client_can_create_invoice(
    *,
    payment,
):
    order = payment.order

    if payment.method != PaymentMethod.INVOICE:
        raise ValidationError(
            "Invoice can be created only for invoice payment method."
        )

    if hasattr(
        payment,
        "invoice",
    ):
        raise ValidationError(
            "Invoice already exists for this payment."
        )

    if order.delivery_method != DeliveryMethod.PICKUP:
        raise ValidationError(
            "Invoice will be available after delivery confirmation by manager."
        )


def validate_manager_can_create_invoice(
    *,
    payment,
):
    if payment.method != PaymentMethod.INVOICE:
        raise ValidationError(
            "Invoice can be created only for invoice payment method."
        )

    if hasattr(
        payment,
        "invoice",
    ):
        raise ValidationError(
            "Invoice already exists for this payment."
        )