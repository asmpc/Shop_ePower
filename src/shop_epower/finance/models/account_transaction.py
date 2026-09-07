from decimal import Decimal

from django.conf import settings
from django.db import models

from shop_epower.finance.models.customer_account import CustomerAccount


class AccountTransactionType(models.TextChoices):
    DEPOSIT = "deposit", "Deposit"
    DEBT_INCREASE = "debt_increase", "Debt increase"
    ALLOCATION = "allocation", "Allocation"
    REFUND = "refund", "Refund"
    REVERSAL = "reversal", "Reversal"


class AccountTransactionActorType(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    MANAGER = "manager", "Manager"
    ADMIN = "admin", "Admin"
    SYSTEM = "system", "System"


class AccountTransaction(models.Model):
    account = models.ForeignKey(
        CustomerAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    operation_type = models.CharField(
        max_length=30,
        choices=AccountTransactionType.choices,
    )

    available_delta = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    debt_delta = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    available_balance_after = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    debt_balance_after = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    currency_snapshot = models.CharField(
        max_length=10,
    )

    operation_key = models.CharField(
        max_length=255,
        unique=True,
    )

    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="reversal",
        null=True,
        blank=True,
    )

    comment = models.TextField(
        blank=True,
    )

    actor_type = models.CharField(
        max_length=20,
        choices=AccountTransactionActorType.choices,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_account_transactions",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=("account", "created_at"),
                name="fin_tx_account_created_idx",
            ),
            models.Index(
                fields=("operation_type",),
                name="fin_tx_operation_type_idx",
            ),
            models.Index(
                fields=("actor_type",),
                name="fin_tx_actor_type_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    available_balance_after__gte=Decimal("0.00"),
                ),
                name=(
                    "account_transaction_"
                    "available_balance_after_nonnegative"
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(
                    debt_balance_after__gte=Decimal("0.00"),
                ),
                name=(
                    "account_transaction_"
                    "debt_balance_after_nonnegative"
                ),
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    available_delta=Decimal("0.00"),
                    debt_delta=Decimal("0.00"),
                ),
                name="account_transaction_nonzero_delta",
            ),
        ]
