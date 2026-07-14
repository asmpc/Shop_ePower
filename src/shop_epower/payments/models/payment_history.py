from django.conf import settings
from django.db import models

from shop_epower.payments.models.payment import (
    Payment,
    PaymentStatus,
)


class PaymentHistory(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="history",
    )

    old_status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
    )

    new_status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
    )

    comment = models.TextField(
        blank=True,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Payment #{self.payment_id}: "
            f"{self.old_status} -> {self.new_status}"
        )