from decimal import Decimal

from django.db import models

from shop_epower.payments.models.customer_payout import CustomerPayout


class CustomerPayoutSource(models.Model):
    payout = models.ForeignKey(
        CustomerPayout,
        on_delete=models.PROTECT,
        related_name="sources",
    )

    deposit_transaction = models.ForeignKey(
        "finance.AccountTransaction",
        on_delete=models.PROTECT,
        related_name="customer_payout_sources",
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "payout",
                    "deposit_transaction",
                ],
                name="customer_payout_source_unique_deposit",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    amount__gt=Decimal("0.00"),
                ),
                name="customer_payout_source_amount_positive",
            ),
        ]