from django.db import models

from shop_epower.payments.models.invoice import Invoice


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="items",
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