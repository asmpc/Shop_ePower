from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from shop_epower.core.currency import get_base_currency
from shop_epower.finance.models import (
    AccountTransaction,
    AccountTransactionActorType,
    AccountTransactionType,
    CustomerAccount,
    CustomerAccountStatus,
)


@transaction.atomic
def _apply_account_transaction(
    *,
    account,
    operation_type,
    available_delta,
    debt_delta,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
    reversal_of=None,
):
    if not isinstance(operation_key, str) or not operation_key.strip():
        raise ValidationError("Operation key is required.")

    if actor_type not in AccountTransactionActorType.values:
        raise ValidationError("Unsupported financial operation actor type.")

    human_actor_types = (
        AccountTransactionActorType.CUSTOMER,
        AccountTransactionActorType.MANAGER,
        AccountTransactionActorType.ADMIN,
    )

    if actor_type in human_actor_types and created_by is None:
        raise ValidationError("created_by is required for human financial operations.")

    locked_account = CustomerAccount.objects.select_for_update().get(
        pk=account.pk,
    )

    existing_transaction = AccountTransaction.objects.filter(
        operation_key=operation_key,
    ).first()

    if locked_account.currency != get_base_currency():
        raise ValidationError(
            "Account currency does not match deployment base currency."
        )

    if existing_transaction is not None:
        transaction_matches_request = (
            existing_transaction.account_id == locked_account.pk
            and existing_transaction.operation_type == operation_type
            and existing_transaction.available_delta == available_delta
            and existing_transaction.debt_delta == debt_delta
            and existing_transaction.actor_type == actor_type
            and existing_transaction.created_by_id == getattr(created_by, "pk", None)
            and existing_transaction.comment == comment
            and existing_transaction.reversal_of_id == getattr(reversal_of, "pk", None)
        )

        if transaction_matches_request:
            return existing_transaction

        raise ValidationError(
            "Operation key is already used for different transaction data."
        )

    if (
        locked_account.status == CustomerAccountStatus.INACTIVE
        and operation_type == AccountTransactionType.DEBT_INCREASE
    ):
        raise ValidationError("Inactive customer account cannot receive new debt.")

    available_balance_after = locked_account.available_balance + available_delta
    debt_balance_after = locked_account.debt_balance + debt_delta

    if available_balance_after < Decimal("0.00"):
        raise ValidationError("Resulting available balance cannot be negative.")

    if debt_balance_after < Decimal("0.00"):
        raise ValidationError("Resulting debt balance cannot be negative.")

    account_transaction = AccountTransaction.objects.create(
        account=locked_account,
        operation_type=operation_type,
        available_delta=available_delta,
        debt_delta=debt_delta,
        available_balance_after=available_balance_after,
        debt_balance_after=debt_balance_after,
        currency_snapshot=locked_account.currency,
        operation_key=operation_key,
        reversal_of=reversal_of,
        comment=comment,
        actor_type=actor_type,
        created_by=created_by,
    )

    locked_account.available_balance = available_balance_after
    locked_account.debt_balance = debt_balance_after
    locked_account.save(
        update_fields=[
            "available_balance",
            "debt_balance",
            "updated_at",
        ]
    )

    return account_transaction


def _validate_positive_amount(amount):
    if not isinstance(amount, Decimal):
        raise ValidationError("Amount must be a Decimal.")

    if not amount.is_finite():
        raise ValidationError("Amount must be finite.")

    if amount <= Decimal("0.00"):
        raise ValidationError("Amount must be greater than zero.")

    if amount != amount.quantize(Decimal("0.01")):
        raise ValidationError("Amount must have no more than two decimal places.")


def record_customer_deposit(
    *,
    account,
    amount,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
):
    _validate_positive_amount(amount)

    return _apply_account_transaction(
        account=account,
        operation_type=AccountTransactionType.DEPOSIT,
        available_delta=amount,
        debt_delta=Decimal("0.00"),
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )


def record_customer_debt(
    *,
    account,
    amount,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
):
    _validate_positive_amount(amount)

    return _apply_account_transaction(
        account=account,
        operation_type=AccountTransactionType.DEBT_INCREASE,
        available_delta=Decimal("0.00"),
        debt_delta=amount,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )


def allocate_customer_funds(
    *,
    account,
    amount,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
):
    _validate_positive_amount(amount)

    return _apply_account_transaction(
        account=account,
        operation_type=AccountTransactionType.ALLOCATION,
        available_delta=-amount,
        debt_delta=-amount,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )


def record_customer_refund(
    *,
    account,
    amount,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
):
    _validate_positive_amount(amount)

    return _apply_account_transaction(
        account=account,
        operation_type=AccountTransactionType.REFUND,
        available_delta=amount,
        debt_delta=Decimal("0.00"),
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )


@transaction.atomic
def reverse_customer_transaction(
    *,
    original_transaction,
    operation_key,
    actor_type,
    created_by=None,
    comment,
):
    if not comment or not comment.strip():
        raise ValidationError("Reversal comment is required.")

    locked_account = CustomerAccount.objects.select_for_update().get(
        pk=original_transaction.account_id,
    )
    locked_original_transaction = AccountTransaction.objects.select_for_update().get(
        pk=original_transaction.pk,
    )

    if locked_original_transaction.currency_snapshot != locked_account.currency:
        raise ValidationError(
            "Original transaction currency does not match account currency."
        )

    if locked_original_transaction.operation_type == AccountTransactionType.REVERSAL:
        raise ValidationError("A reversal transaction cannot be reversed.")

    existing_reversal = AccountTransaction.objects.filter(
        reversal_of=locked_original_transaction,
    ).first()

    if (
        existing_reversal is not None
        and existing_reversal.operation_key != operation_key
    ):
        raise ValidationError("Transaction has already been reversed.")

    return _apply_account_transaction(
        account=locked_account,
        operation_type=AccountTransactionType.REVERSAL,
        available_delta=(-locked_original_transaction.available_delta),
        debt_delta=(-locked_original_transaction.debt_delta),
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
        reversal_of=locked_original_transaction,
    )
