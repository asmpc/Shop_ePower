from django.core.exceptions import ValidationError

from shop_epower.orders.models import (
    DeliveryMethod,
    OrderStatus,
)
from shop_epower.payments.models import (
    PaymentMethod,
)


def validate_order_ready_for_invoice(
    *,
    order,
):
    if order.status != OrderStatus.PROCESSING:
        raise ValidationError(
            "Invoice can be generated only for an order in processing."
        )

    if order.delivery_method != DeliveryMethod.SHIPPING:
        return

    if not order.delivery_provider:
        raise ValidationError(
            "Delivery provider must be selected before generating invoice."
        )

    if not order.delivery_address:
        raise ValidationError(
            "Delivery address must be specified before generating invoice."
        )

    if order.delivery_cost is None:
        raise ValidationError(
            "Delivery cost must be calculated before generating invoice."
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

    validate_order_ready_for_invoice(
        order=payment.order,
    )