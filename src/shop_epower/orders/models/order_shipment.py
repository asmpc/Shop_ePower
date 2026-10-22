from decimal import Decimal

from django.conf import settings
from django.db import models

from shop_epower.orders.models.order import Order


class OrderShipment(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="shipments",
    )

    customer_account = models.ForeignKey(
        "finance.CustomerAccount",
        on_delete=models.PROTECT,
        related_name="shipments",
    )

    debt_transaction = models.OneToOneField(
        "finance.AccountTransaction",
        on_delete=models.PROTECT,
        related_name="order_shipment",
    )

    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    currency_snapshot = models.CharField(
        max_length=10,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_order_shipments",
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
            models.UniqueConstraint(
                fields=["order"],
                name="order_shipment_unique_order",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total_amount__gt=Decimal("0.00"),
                ),
                name="order_shipment_amount_positive",
            ),
        ]