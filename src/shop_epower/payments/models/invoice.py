from django.conf import settings
from django.db import models

from shop_epower.orders.models import Order
from shop_epower.payments.models.payment import Payment


class InvoiceStatus(models.TextChoices):
    ISSUED = "issued", "Issued"
    CANCELLED = "cancelled", "Cancelled"

class Invoice(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="invoice",
    )

    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name="invoice",
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
    )

    status = models.CharField(
        max_length=30,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.ISSUED,
    )

    # Seller snapshot

    seller_company_name = models.CharField(
        max_length=255,
    )

    seller_short_company_name = models.CharField(
        max_length=255,
        blank=True,
    )

    seller_tax_id = models.CharField(
        max_length=100,
    )

    seller_tax_registration_reason_code = models.CharField(
        max_length=100,
        blank=True,
    )

    seller_state_registration_number = models.CharField(
        max_length=100,
        blank=True,
    )

    seller_legal_address = models.TextField()

    seller_actual_address = models.TextField(
        blank=True,
    )

    seller_bank_name = models.CharField(
        max_length=255,
    )

    seller_bank_account = models.CharField(
        max_length=255,
    )

    seller_bank_code = models.CharField(
        max_length=100,
        blank=True,
    )

    seller_correspondent_account = models.CharField(
        max_length=255,
        blank=True,
    )

    seller_phone = models.CharField(
        max_length=100,
        blank=True,
    )

    seller_email = models.EmailField(
        blank=True,
    )

    # Buyer snapshot

    buyer_name = models.CharField(
        max_length=255,
        blank=True,
    )

    buyer_email = models.EmailField(
        blank=True,
    )

    buyer_phone = models.CharField(
        max_length=100,
        blank=True,
    )

    buyer_address = models.TextField(
        blank=True,
    )

    buyer_is_legal_entity = models.BooleanField(
        default=False,
    )

    buyer_company_name = models.CharField(
        max_length=255,
        blank=True,
    )

    buyer_tax_id = models.CharField(
        max_length=100,
        blank=True,
    )

    buyer_legal_address = models.TextField(
        blank=True,
    )

    buyer_bank_name = models.CharField(
        max_length=255,
        blank=True,
    )

    buyer_bank_account = models.CharField(
        max_length=255,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency_snapshot = models.CharField(
        max_length=10,
    )

    cancel_comment = models.TextField(
        blank=True,
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

    def __str__(self):
        return (
            f"Invoice {self.invoice_number} "
            f"for Order #{self.order_id}"
        )

