from django.core.exceptions import ValidationError
from django.db import transaction

from shop_epower.accounts.models import Role
from shop_epower.finance.models import (
    AccountTransaction,
    AccountTransactionActorType,
    CustomerAccount,
    CustomerAccountType,
)
from shop_epower.finance.services import (
    record_customer_deposit,
    reverse_customer_transaction,
)
from shop_epower.orders.models import Order
from shop_epower.payments.choices import PaymentMethod
from shop_epower.payments.models import (
    Payment,
    PaymentHistory,
    PaymentProvider,
    PaymentStatus,
)


def _validate_manual_receipt_request(
    *,
    created_by,
    operation_key,
    method,
):
    """Проверяет общие условия регистрации ручного поступления."""

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

def _create_manual_receipt_payment(
    *,
    order,
    deposit,
    amount,
    method,
    comment,
):
    """Создаёт Payment для подтверждённого ручного поступления."""

    return Payment.objects.create(
        order=order,
        deposit_transaction=deposit,
        amount=amount,
        method=method,
        status=PaymentStatus.PAID,
        provider=PaymentProvider.MANUAL,
        currency_snapshot=deposit.currency_snapshot,
        manager_comment=comment,
    )

@transaction.atomic
def record_manual_account_payment(
    *,
    account,
    amount,
    method,
    operation_key,
    created_by,
    comment="",
):
    """Регистрирует подтверждённое поступление на счёт без заказа."""

    _validate_manual_receipt_request(
        created_by=created_by,
        operation_key=operation_key,
        method=method,
    )

    if getattr(account, "pk", None) is None:
        raise ValidationError(
            "Customer account must be saved before recording payment."
        )

    # Блокируем сохранённый счёт до проверки занятого ключа.
    locked_account = CustomerAccount.objects.select_for_update().get(
        pk=account.pk,
    )

    existing_deposit = AccountTransaction.objects.filter(
        operation_key=operation_key,
    ).first()

    # Проверяем, допускает ли существующая операция повтор регистрации.
    if existing_deposit is not None:
        if not Payment.objects.filter(
            deposit_transaction=existing_deposit,
        ).exists():
            raise ValidationError(
                "Operation key is already used for different payment data."
            )

        if AccountTransaction.objects.filter(
            reversal_of=existing_deposit,
        ).exists():
            raise ValidationError(
                "Payment deposit has already been reversed."
            )

    actor_type = (
        AccountTransactionActorType.ADMIN
        if created_by.role == Role.ADMIN
        else AccountTransactionActorType.MANAGER
    )

    # Финансовое ядро проверяет сумму, создаёт пополнение
    # и обновляет доступный баланс счёта.
    deposit = record_customer_deposit(
        account=locked_account,
        amount=amount,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )

    # При повторе финансовое ядро возвращает прежнее пополнение.
    # Если Payment уже создан, возвращаем его.
    existing_payment = Payment.objects.filter(
        deposit_transaction=deposit,
    ).first()

    if existing_payment is not None:
        if (
            existing_payment.order_id is not None
            or existing_payment.method != method
        ):
            raise ValidationError(
                "Operation key is already used for different payment data."
            )

        return existing_payment

    # Поступление связано со счётом через финансовую операцию.
    # Заказ для него не создаётся.
    return _create_manual_receipt_payment(
        order=None,
        deposit=deposit,
        amount=amount,
        method=method,
        comment=comment,
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

    _validate_manual_receipt_request(
        created_by=created_by,
        operation_key=operation_key,
        method=method,
    )

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

    return _create_manual_receipt_payment(
        order=locked_order,
        deposit=deposit,
        amount=amount,
        method=method,
        comment=comment,
    )

@transaction.atomic
def cancel_manual_order_payment(
    *,
    payment,
    operation_key,
    created_by,
    comment,
):
    """Отменяет ошибочно зарегистрированное ручное поступление."""

    if (
        getattr(created_by, "pk", None) is None
        or not created_by.is_active
        or created_by.role not in (Role.MANAGER, Role.ADMIN)
    ):
        raise ValidationError(
            "Only managers and administrators can cancel receipts."
        )

    locked_payment = Payment.objects.select_for_update().get(
        pk=payment.pk,
    )

    if (
            locked_payment.status not in (
            PaymentStatus.PAID,
            PaymentStatus.CANCELLED,
    )
            or locked_payment.provider != PaymentProvider.MANUAL
            or locked_payment.deposit_transaction_id is None
    ):
        raise ValidationError(
            "Only confirmed manual receipts with a deposit can be cancelled."
        )

    deposit = locked_payment.deposit_transaction

    if locked_payment.amount != deposit.available_delta:
        raise ValidationError(
            "Payment amount does not match its deposit."
        )

    if locked_payment.currency_snapshot != deposit.currency_snapshot:
        raise ValidationError(
            "Payment currency does not match its deposit."
        )

    if (
        locked_payment.order_id is not None
        and locked_payment.order.customer_account_id != deposit.account_id
    ):
        raise ValidationError(
            "Payment order account does not match its deposit account."
        )

    # Назначение средств тоже блокирует этот счёт.
    # Берём блокировку до проверки зависимых назначений.
    CustomerAccount.objects.select_for_update().get(
        pk=deposit.account_id,
    )

    if (
        locked_payment.status == PaymentStatus.CANCELLED
        and not AccountTransaction.objects.filter(
            reversal_of=deposit,
        ).exists()
    ):
        raise ValidationError(
            "Cancelled receipt must have a reversed deposit."
        )

    if deposit.order_fund_assignment_sources.filter(
        assignment__account_transaction__reversal__isnull=True,
    ).exists():
        raise ValidationError(
            "Cancel dependent fund assignments before cancelling the receipt."
        )

    actor_type = (
        AccountTransactionActorType.ADMIN
        if created_by.role == Role.ADMIN
        else AccountTransactionActorType.MANAGER
    )

    # Финансовое ядро создаёт сторно исходного пополнения
    # и пересчитывает баланс счёта.
    reverse_customer_transaction(
        original_transaction=deposit,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )

    # Финансовое ядро уже проверило соответствие повторного запроса.
    # Смена статуса и запись истории выполнены при первой отмене.
    if locked_payment.status == PaymentStatus.CANCELLED:
        return locked_payment

    old_status = locked_payment.status

    locked_payment.status = PaymentStatus.CANCELLED
    locked_payment.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    PaymentHistory.objects.create(
        payment=locked_payment,
        old_status=old_status,
        new_status=locked_payment.status,
        comment=comment,
        changed_by=created_by,
    )

    return locked_payment