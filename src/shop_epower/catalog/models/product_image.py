from django.db import models
from django.utils.translation import gettext_lazy as _

from shop_epower.core.models import BaseModel


class ProductImage(BaseModel):

    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='images',
        null=True,
        blank=True,
        verbose_name=_('Product')
    )

    image = models.ImageField(
        upload_to='products/',
        verbose_name=_('Image')
    )

    alt_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Alt text')
    )

    is_primary = models.BooleanField(
        default=False,
        verbose_name=_('Is primary')
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Sort order')
    )

    class Meta:

        verbose_name = _('Product image')
        verbose_name_plural = _('Product images')

        ordering = ['sort_order']

        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['is_primary']),
        ]

    def __str__(self):
        return f"Image for {self.product}"