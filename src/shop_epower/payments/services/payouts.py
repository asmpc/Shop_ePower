from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Subquery, Sum

from shop_epower.accounts.models import Role
from shop_epower.finance.models import (
    AccountTransaction,
    AccountTransactionActorType,
    AccountTransactionType,
    CustomerAccount,
)
from shop_epower.finance.services import record_customer_payout
from shop_epower.orders.models import OrderFundAssignmentSource
from shop_epower.payments.models import (
    CustomerPayout,
    CustomerPayoutSource,
    PayoutMethod,
)


def _get_payout_deposits(account):
    active_assignments = (
        OrderFundAssignmentSource.objects.filter(
            deposit_transaction_id=OuterRef("pk"),
            assignment__account_transaction__reversal__isnull=True,
        )
        .order_by()
        .values("deposit_transaction_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    previous_payouts = (
        CustomerPayoutSource.objects.filter(
            deposit_transaction_id=OuterRef("pk"),
        )
        .order_by()
        .values("deposit_transaction_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    return (
        account.transactions.filter(
            operation_type=AccountTransactionType.DEPOSIT,
            currency_snapshot=account.currency,
            reversal__isnull=True,
        )
        .annotate(
            assigned_amount=Subquery(active_assignments),
            paid_out_amount=Subquery(previous_payouts),
        )
        .order_by("-created_at", "-pk")
    )

@transaction.atomic
def record_manual_account_payout(
    *,
    account,
    amount,
    method,
    operation_key,
    created_by,
    comment="",
):
    if (
        getattr(created_by, "pk", None) is None
        or not created_by.is_active
        or created_by.role not in (Role.MANAGER, Role.ADMIN)
    ):
        raise ValidationError(
            "Only managers and administrators can record payouts."
        )

    if method not in PayoutMethod.values:
        raise ValidationError("Unsupported manual payout method.")

    if not isinstance(operation_key, str) or not operation_key.strip():
        raise ValidationError("Operation key is required.")

    if len(operation_key) > 255:
        raise ValidationError("Operation key is too long.")

    if getattr(account, "pk", None) is None:
        raise ValidationError(
            "Customer account must be saved before recording payout."
        )

    locked_account = CustomerAccount.objects.select_for_update().get(
        pk=account.pk,
    )

    existing_transaction = AccountTransaction.objects.filter(
        operation_key=operation_key,
    ).first()

    existing_payout = None

    if existing_transaction is not None:
        existing_payout = CustomerPayout.objects.filter(
            account_transaction=existing_transaction,
        ).first()

        if existing_payout is None or existing_payout.method != method:
            raise ValidationError(
                "Operation key is already used for different payout data."
            )

    actor_type = (
        AccountTransactionActorType.ADMIN
        if created_by.role == Role.ADMIN
        else AccountTransactionActorType.MANAGER
    )

    payout_transaction = record_customer_payout(
        account=locked_account,
        amount=amount,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )

    if existing_payout is not None:
        return existing_payout

    remaining_amount = amount
    source_parts = []

    for deposit in _get_payout_deposits(locked_account).iterator(chunk_size=100):
        assigned_amount = deposit.assigned_amount or Decimal("0.00")
        paid_out_amount = deposit.paid_out_amount or Decimal("0.00")

        free_amount = (
            deposit.available_delta
            - assigned_amount
            - paid_out_amount
        )

        if free_amount <= Decimal("0.00"):
            continue

        part_amount = min(free_amount, remaining_amount)
        source_parts.append((deposit, part_amount))
        remaining_amount -= part_amount

        if remaining_amount == Decimal("0.00"):
            break

    if remaining_amount > Decimal("0.00"):
        raise ValidationError(
            "Not enough unassigned deposit funds for payout."
        )

    payout = CustomerPayout.objects.create(
        account_transaction=payout_transaction,
        amount=amount,
        method=method,
    )

    for deposit, part_amount in source_parts:
        CustomerPayoutSource.objects.create(
            payout=payout,
            deposit_transaction=deposit,
            amount=part_amount,
        )

    return payout