from decimal import Decimal

from django.db import models

from shop_epower.orders.models.order import Order


class OrderFundAssignment(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="fund_assignments",
    )

    account_transaction = models.OneToOneField(
        "finance.AccountTransaction",
        on_delete=models.PROTECT,
        related_name="order_fund_assignment",
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
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
                name="order_fund_assignment_amount_positive",
            ),
        ]

    def __str__(self):
        return (
            f"Fund assignment #{self.pk} "
            f"for Order #{self.order_id}"
        )