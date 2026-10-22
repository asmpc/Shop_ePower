from django.db import models

from shop_epower.orders.models.order_item import OrderItem
from shop_epower.orders.models.order_shipment import OrderShipment


class OrderShipmentItem(models.Model):
    shipment = models.ForeignKey(
        OrderShipment,
        on_delete=models.PROTECT,
        related_name="items",
    )

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.PROTECT,
        related_name="shipment_items",
    )

    product_name = models.CharField(
        max_length=255,
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    quantity = models.PositiveIntegerField()

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency_snapshot = models.CharField(
        max_length=10,
    )

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    quantity__gt=0,
                ),
                name="order_shipment_item_quantity_positive",
            ),
            models.UniqueConstraint(
                fields=["shipment", "order_item"],
                name="shipment_item_unique_order_item",
            ),
        ]