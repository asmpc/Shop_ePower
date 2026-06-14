from django.core.exceptions import ValidationError
from shop_epower.payments.models import (
    Payment,
    PaymentHistory,
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

def _create_payment_history(
    *,
    payment,
    old_status,
    new_status,
    comment="",
    changed_by=None,
):
    PaymentHistory.objects.create(
        payment=payment,
        old_status=old_status,
        new_status=new_status,
        comment=comment,
        changed_by=changed_by,
    )

def mark_payment_paid(
    *,
    payment,
    manager_comment="",
    changed_by=None,
):
    """
    Переводит payment в статус PAID.

    Пока меняем только сам payment.
    Order status подключим позже отдельным шагом.
    """

    _validate_payment_is_pending(payment)

    old_status = payment.status

    payment.status = PaymentStatus.PAID
    payment.manager_comment = manager_comment

    payment.save(
        update_fields=[
            "status",
            "manager_comment",
            "updated_at",
        ]
    )

    _create_payment_history(
        payment=payment,
        old_status=old_status,
        new_status=PaymentStatus.PAID,
        comment=manager_comment,
        changed_by=changed_by,
    )

    return payment


def mark_payment_failed(
    *,
    payment,
    manager_comment="",
    changed_by=None,
):
    """
    Переводит payment в статус FAILED.

    Используется для неуспешной оплаты.
    """

    _validate_payment_is_pending(payment)

    old_status = payment.status

    payment.status = PaymentStatus.FAILED
    payment.manager_comment = manager_comment

    payment.save(
        update_fields=[
            "status",
            "manager_comment",
            "updated_at",
        ]
    )

    _create_payment_history(
        payment=payment,
        old_status=old_status,
        new_status=PaymentStatus.FAILED,
        comment=manager_comment,
        changed_by=changed_by,
    )

    return payment


def mark_payment_cancelled(
    *,
    payment,
    manager_comment="",
    changed_by=None,
):
    """
    Переводит payment в статус CANCELLED.

    Используется, если оплату отменили.
    """

    _validate_payment_is_pending(payment)

    old_status = payment.status

    payment.status = PaymentStatus.CANCELLED
    payment.manager_comment = manager_comment

    payment.save(
        update_fields=[
            "status",
            "manager_comment",
            "updated_at",
        ]
    )

    _create_payment_history(
        payment=payment,
        old_status=old_status,
        new_status=PaymentStatus.CANCELLED,
        comment=manager_comment,
        changed_by=changed_by,
    )

    return payment

def reset_payment_to_pending(
    *,
    payment,
    manager_comment="",
    changed_by=None,
):
    if payment.status == PaymentStatus.PENDING:
        raise ValidationError(
            "Only non-pending payment can be reset to pending."
        )

    old_status = payment.status

    payment.status = PaymentStatus.PENDING
    payment.manager_comment = manager_comment

    payment.save(
        update_fields=[
            "status",
            "manager_comment",
            "updated_at",
        ]
    )

    _create_payment_history(
        payment=payment,
        old_status=old_status,
        new_status=PaymentStatus.PENDING,
        comment=manager_comment,
        changed_by=changed_by,
    )

    return payment