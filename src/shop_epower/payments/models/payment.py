from django.db import models
from django.utils.crypto import get_random_string

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import Order


class PaymentMethod(models.TextChoices):
    ON_RECEIPT = "on_receipt", "On receipt"
    INVOICE = "invoice", "By invoice"
    ONLINE = "online", "Online payment"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class PaymentProvider(models.TextChoices):
    MANUAL = "manual", "Manual"
    MOCK = "mock", "Mock provider"


class Payment(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="payment",
    )

    method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
    )

    status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    provider = models.CharField(
        max_length=30,
        choices=PaymentProvider.choices,
        default=PaymentProvider.MANUAL,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency_snapshot = models.CharField(
        max_length=10,
        default=get_base_currency,
    )

    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
    )

    provider_payment_id = models.CharField(
        max_length=255,
        blank=True,
    )

    manager_comment = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = get_random_string(32)

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Payment #{self.pk} "
            f"for Order #{self.order_id} "
            f"({self.status})"
        )