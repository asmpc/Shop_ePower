from django.conf import settings
from django.db import models

from shop_epower.orders.models.order import Order


class OrderItemChangeType(models.TextChoices):
    ADDED = "added", "Added"
    REDUCED = "reduced", "Reduced"
    REMOVED = "removed", "Removed"


class OrderItemChange(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="item_changes",
    )

    order_item_id_snapshot = models.PositiveBigIntegerField()

    change_type = models.CharField(
        max_length=20,
        choices=OrderItemChangeType.choices,
    )

    product_name = models.CharField(
        max_length=255,
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    old_quantity = models.PositiveIntegerField()

    new_quantity = models.PositiveIntegerField()

    old_order_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    new_order_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency_snapshot = models.CharField(
        max_length=10,
    )

    reservations_before = models.JSONField(
        default=list,
    )

    reservations_after = models.JSONField(
        default=list,
    )

    reason = models.TextField()

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="order_item_changes",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
