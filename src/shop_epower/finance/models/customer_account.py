from decimal import Decimal

from django.conf import settings
from django.db import models

from shop_epower.core.currency import get_base_currency


class CustomerAccountType(models.TextChoices):
    PERSONAL = "personal", "Personal"
    LEGAL = "legal", "Legal"


class CustomerAccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class CustomerAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="financial_accounts",
    )

    account_type = models.CharField(
        max_length=20,
        choices=CustomerAccountType.choices,
    )

    legal_profile = models.OneToOneField(
        "accounts.LegalProfile",
        on_delete=models.PROTECT,
        related_name="financial_account",
        null=True,
        blank=True,
    )

    legal_tax_id_snapshot = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    currency = models.CharField(
        max_length=10,
        default=get_base_currency,
    )

    available_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    debt_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    status = models.CharField(
        max_length=20,
        choices=CustomerAccountStatus.choices,
        default=CustomerAccountStatus.ACTIVE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=("user", "status"),
                name="fin_acc_user_status_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "user",
                    "account_type",
                ),
                name="unique_customer_account_type_per_user",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    available_balance__gte=Decimal("0.00"),
                ),
                name="customer_account_available_balance_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    debt_balance__gte=Decimal("0.00"),
                ),
                name="customer_account_debt_balance_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        account_type=CustomerAccountType.LEGAL,
                    )
                    | models.Q(
                        legal_profile__isnull=True,
                    )
                ),
                name="personal_account_without_legal_profile",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        account_type=CustomerAccountType.PERSONAL,
                    )
                    | models.Q(
                        legal_profile__isnull=False,
                    )
                ),
                name="legal_account_with_legal_profile",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        account_type=CustomerAccountType.LEGAL,
                    )
                    | models.Q(
                        legal_tax_id_snapshot="",
                    )
                ),
                name="personal_account_without_legal_tax_id_snapshot",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        account_type=CustomerAccountType.PERSONAL,
                    )
                    | ~models.Q(
                        legal_tax_id_snapshot="",
                    )
                ),
                name="legal_account_with_legal_tax_id_snapshot",
            ),
        ]
