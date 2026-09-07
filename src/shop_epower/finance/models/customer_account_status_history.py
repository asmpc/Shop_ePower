from django.conf import settings
from django.db import models

from shop_epower.finance.models.customer_account import (
    CustomerAccount,
    CustomerAccountStatus,
)


class CustomerAccountStatusHistory(models.Model):
    account = models.ForeignKey(
        CustomerAccount,
        on_delete=models.PROTECT,
        related_name="status_history",
    )

    old_status = models.CharField(
        max_length=20,
        choices=CustomerAccountStatus.choices,
    )

    new_status = models.CharField(
        max_length=20,
        choices=CustomerAccountStatus.choices,
    )

    reason = models.TextField()

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_account_status_changes",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=("account", "created_at"),
                name="fin_status_acct_created_idx",
            ),
        ]
