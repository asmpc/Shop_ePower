from decimal import Decimal

from django.db import models

from shop_epower.orders.models.order_fund_assignment import OrderFundAssignment
from shop_epower.orders.models.order_shipment import OrderShipment


class OrderFundApplication(models.Model):
    assignment = models.ForeignKey(
        OrderFundAssignment,
        on_delete=models.PROTECT,
        related_name="applications",
    )

    shipment = models.ForeignKey(
        OrderShipment,
        on_delete=models.PROTECT,
        related_name="fund_applications",
    )

    account_transaction = models.OneToOneField(
        "finance.AccountTransaction",
        on_delete=models.PROTECT,
        related_name="order_fund_application",
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
                name="order_fund_application_amount_positive",
            ),
        ]