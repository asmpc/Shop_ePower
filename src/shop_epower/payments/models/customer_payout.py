from decimal import Decimal

from django.db import models


class PayoutMethod(models.TextChoices):
    CASH = "cash", "Cash"
    BANK_TRANSFER = "bank_transfer", "Bank transfer"


class CustomerPayout(models.Model):
    account_transaction = models.OneToOneField(
        "finance.AccountTransaction",
        on_delete=models.PROTECT,
        related_name="customer_payout",
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    method = models.CharField(
        max_length=30,
        choices=PayoutMethod.choices,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
            "-pk",
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    amount__gt=Decimal("0.00"),
                ),
                name="customer_payout_amount_positive",
            ),
        ]