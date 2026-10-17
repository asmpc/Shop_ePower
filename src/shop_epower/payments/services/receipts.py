from django.core.exceptions import ValidationError
from django.db import transaction

from shop_epower.accounts.models import Role
from shop_epower.finance.models import (
    AccountTransaction,
    AccountTransactionActorType,
    CustomerAccount,
    CustomerAccountType,
)
from shop_epower.finance.services import record_customer_deposit
from shop_epower.orders.models import Order
from shop_epower.payments.choices import PaymentMethod
from shop_epower.payments.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
)


@transaction.atomic
def record_manual_order_payment(
    *,
    order,
    amount,
    method,
    operation_key,
    created_by,
    comment="",
):
    """Регистрирует подтверждённое поступление без распределения денег."""

    # Подтверждать поступление может только активный сотрудник.
    if (
        getattr(created_by, "pk", None) is None
        or not created_by.is_active
        or created_by.role not in (Role.MANAGER, Role.ADMIN)
    ):
        raise ValidationError(
            "Only managers and administrators can record payments."
        )

    if not isinstance(operation_key, str) or not operation_key.strip():
        raise ValidationError("Operation key is required.")

    if len(operation_key) > 255:
        raise ValidationError("Operation key is too long.")

    if method not in (PaymentMethod.ON_RECEIPT, PaymentMethod.INVOICE):
        raise ValidationError("Unsupported manual payment method.")

    if getattr(order, "pk", None) is None:
        raise ValidationError("Order must be saved before recording payment.")

    # Используем сохранённые данные заказа, а не состояние объекта вызывающего кода.
    locked_order = Order.objects.select_for_update().get(pk=order.pk)

    account_type = (
        CustomerAccountType.LEGAL
        if locked_order.is_legal_entity
        else CustomerAccountType.PERSONAL
    )

    account = (
        CustomerAccount.objects.select_for_update()
        .filter(
            pk=locked_order.customer_account_id,
            user_id=locked_order.user_id,
            account_type=account_type,
        )
        .first()
    )

    if account is None:
        raise ValidationError(
            "Order must reference its owner's matching customer account."
        )

    if locked_order.currency_snapshot != account.currency:
        raise ValidationError("Order currency must match account currency.")

    actor_type = (
        AccountTransactionActorType.ADMIN
        if created_by.role == Role.ADMIN
        else AccountTransactionActorType.MANAGER
    )

    # Повтор ключа должен соответствовать тому же платежу.
    existing_deposit = AccountTransaction.objects.filter(
        operation_key=operation_key,
    ).first()

    existing_payment = None

    if existing_deposit is not None:
        existing_payment = Payment.objects.filter(
            deposit_transaction=existing_deposit,
        ).first()

        payment_matches_request = (
            existing_payment is not None
            and existing_payment.order_id == locked_order.pk
            and existing_payment.amount == amount
            and existing_payment.method == method
            and existing_payment.currency_snapshot == account.currency
            and existing_payment.provider == PaymentProvider.MANUAL
            and existing_payment.status == PaymentStatus.PAID
            and existing_payment.manager_comment == comment
        )

        if not payment_matches_request:
            raise ValidationError(
                "Operation key is already used for different payment data."
            )

        if AccountTransaction.objects.filter(
            reversal_of=existing_deposit,
        ).exists():
            raise ValidationError("Payment deposit has already been reversed.")

    # Финансовое ядро проверяет сумму, записывает операцию и обновляет баланс.
    deposit = record_customer_deposit(
        account=account,
        amount=amount,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )

    if existing_payment is not None:
        return existing_payment

    return Payment.objects.create(
        order=locked_order,
        deposit_transaction=deposit,
        amount=amount,
        method=method,
        status=PaymentStatus.PAID,
        provider=PaymentProvider.MANUAL,
        currency_snapshot=account.currency,
        manager_comment=comment,
    )