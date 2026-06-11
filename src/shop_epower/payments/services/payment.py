from django.core.exceptions import ValidationError
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)



def create_payment_for_order(
    *,
    order,
    method,
):
    """
    Создает payment для заказа.

    На этом этапе:
    - сумма берется из order.total_price;
    - валюта берется из order.currency_snapshot;
    - provider выбирается по способу оплаты.
    """

    if method == PaymentMethod.ONLINE:
        provider = PaymentProvider.MOCK
    else:
        provider = PaymentProvider.MANUAL

    return Payment.objects.create(
        order=order,
        method=method,
        provider=provider,
        amount=order.total_price,
        currency_snapshot=order.currency_snapshot,
    )

def _validate_payment_is_pending(payment):
    if payment.status != PaymentStatus.PENDING:
        raise ValidationError(
            "Only pending payment can be updated."
        )


def mark_payment_paid(
    *,
    payment,
    manager_comment="",
):
    """
    Переводит payment в статус PAID.

    Пока меняем только сам payment.
    Order status подключим позже отдельным шагом.
    """

    _validate_payment_is_pending(payment)

    payment.status = PaymentStatus.PAID
    payment.manager_comment = manager_comment

    payment.save(
        update_fields=[
            "status",
            "manager_comment",
            "updated_at",
        ]
    )

    return payment


def mark_payment_failed(
    *,
    payment,
    manager_comment="",
):
    """
    Переводит payment в статус FAILED.

    Используется для неуспешной оплаты.
    """

    _validate_payment_is_pending(payment)

    payment.status = PaymentStatus.FAILED
    payment.manager_comment = manager_comment

    payment.save(
        update_fields=[
            "status",
            "manager_comment",
            "updated_at",
        ]
    )

    return payment


def mark_payment_cancelled(
    *,
    payment,
    manager_comment="",
):
    """
    Переводит payment в статус CANCELLED.

    Используется, если оплату отменили.
    """

    _validate_payment_is_pending(payment)

    payment.status = PaymentStatus.CANCELLED
    payment.manager_comment = manager_comment

    payment.save(
        update_fields=[
            "status",
            "manager_comment",
            "updated_at",
        ]
    )

    return payment