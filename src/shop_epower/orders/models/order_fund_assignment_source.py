from decimal import Decimal

from django.db import models

from shop_epower.orders.models.order_fund_assignment import OrderFundAssignment


class OrderFundAssignmentSource(models.Model):
    assignment = models.ForeignKey(
        OrderFundAssignment,
        on_delete=models.PROTECT,
        related_name="sources",
    )

    deposit_transaction = models.ForeignKey(
        "finance.AccountTransaction",
        on_delete=models.PROTECT,
        related_name="order_fund_assignment_sources",
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    amount__gt=Decimal("0.00"),
                ),
                name="order_fund_assignment_source_amount_positive",
            ),
            models.UniqueConstraint(
                fields=[
                    "assignment",
                    "deposit_transaction",
                ],
                name="order_fund_assignment_source_unique_deposit",
            ),
        ]