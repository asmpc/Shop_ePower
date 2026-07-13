from django.db import models


class CompanySettings(models.Model):
    company_name = models.CharField(
        max_length=255,
    )

    short_company_name = models.CharField(
        max_length=255,
        blank=True,
    )

    tax_id = models.CharField(
        max_length=100,
    )

    tax_registration_reason_code = models.CharField(
        max_length=100,
        blank=True,
    )

    state_registration_number = models.CharField(
        max_length=100,
        blank=True,
    )

    legal_address = models.TextField()

    actual_address = models.TextField(
        blank=True,
    )

    bank_name = models.CharField(
        max_length=255,
    )

    bank_account = models.CharField(
        max_length=255,
    )

    bank_code = models.CharField(
        max_length=100,
        blank=True,
    )

    correspondent_account = models.CharField(
        max_length=255,
        blank=True,
    )

    phone = models.CharField(
        max_length=100,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Company settings"
        verbose_name_plural = "Company settings"

    def __str__(self):
        return self.company_name