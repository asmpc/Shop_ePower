from django.db import models

class CurrencyRate(models.Model):
    CURRENCY_CHOICES = [
        ('RUB', 'RUB'),
        ('USD', 'USD'),
    ]

    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        unique=True
    )

    rate_to_BYN = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        help_text=(
            "Введите курс так: 1 единица выбранной валюты = X BYN. "
            "Например: 1 RUB = 0.038700 BYN, 1 USD = 3.250000 BYN."
        ),
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Currency Rate"
        verbose_name_plural = "Currency Rates"

    def __str__(self):
        return f"{self.currency}: {self.rate_to_BYN}"