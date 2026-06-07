from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _

from shop_epower.core.models import BaseModel
from .cart import Cart


class CartItem(BaseModel):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Cart"),
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name=_("Product"),
    )

    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Quantity"),
    )

    price_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Price snapshot"),
    )

    currency_snapshot = models.CharField(
        max_length=3,
        default="BYN",
        verbose_name=_("Currency snapshot"),
    )

    class Meta:
        verbose_name = _("Cart item")
        verbose_name_plural = _("Cart items")

        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="unique_cart_product",
            ),
        ]

        indexes = [
            models.Index(fields=["cart"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        return f"{self.product} x {self.quantity}"

    @property
    def total_price(self):
        return self.price_snapshot * self.quantity