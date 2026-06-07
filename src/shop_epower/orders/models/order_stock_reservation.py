from django.db import models

from shop_epower.orders.models.order_item import OrderItem


class OrderStockReservation(models.Model):
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="stock_reservations",
    )

    supplier_product = models.ForeignKey(
        "suppliers.SupplierProduct",
        on_delete=models.PROTECT,
        related_name="order_stock_reservations",
    )

    quantity = models.PositiveIntegerField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return (
            f"{self.order_item.product_name} "
            f"x {self.quantity}"
        )