from django.db import models

from shop_epower.catalog.models import Category


class CategoryMarkup(models.Model):
    category = models.OneToOneField(
        Category,
        on_delete=models.CASCADE,
        related_name="markup",
    )

    percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Markup percent for this category.",
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
        verbose_name = "Category Markup"
        verbose_name_plural = "Category Markups"

    def __str__(self):
        return f"{self.category.name}: {self.percent}%"