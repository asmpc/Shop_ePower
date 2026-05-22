from django.db import models

from shop_epower.catalog.models import Product
from shop_epower.suppliers.models.supplier import Supplier


class SupplierProduct(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="supplier_products",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="supplier_products",
    )

    supplier_article = models.CharField(
        max_length=255,
    )

    supplier_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    stock_quantity = models.PositiveIntegerField(
        default=0,
    )

    lead_time_days = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["supplier", "product"]
        unique_together = (
            "supplier",
            "product",
            "supplier_article",
        )

    def __str__(self):
        return f"{self.supplier} → {self.product}"