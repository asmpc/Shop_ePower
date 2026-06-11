from django.core.exceptions import ValidationError

from shop_epower.orders.models import (
    DeliveryMethod,
    OrderStatus,
)
from shop_epower.payments.models import PaymentMethod


def validate_payment_method_for_delivery(
    *,
    delivery_method,
    payment_method,
):
    """
    Проверяет допустимость способа оплаты
    для выбранного способа доставки.
    """

    if (
        delivery_method == DeliveryMethod.SHIPPING
        and payment_method == PaymentMethod.ON_RECEIPT
    ):
        raise ValidationError(
            "Payment on receipt is allowed only for pickup."
        )


def validate_client_can_pay_online(
    *,
    order,
):
    """
    Проверяет, может ли клиент запустить online payment
    для текущего заказа.
    """

    if order.status not in [
        OrderStatus.NEW,
        OrderStatus.PROCESSING,
    ]:
        raise ValidationError(
            "Online payment is available only for new or processing orders."
        )