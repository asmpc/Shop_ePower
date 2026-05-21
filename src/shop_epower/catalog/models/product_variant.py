from django.utils.translation import gettext_lazy as _

from shop_epower.core.models import BaseModel

import uuid
from django.db import models

class ProductVariant(BaseModel):

    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name=_('Product')
    )

    name = models.CharField(
        max_length=255,
        verbose_name=_('Variant name')
    )

    color = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Color')
    )

    internal_code = models.UUIDField(
        unique=True,
        editable=False,
        default=uuid.uuid4,
        verbose_name='Internal code'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is active')
    )

    class Meta:

        verbose_name = _('Product variant')
        verbose_name_plural = _('Product variants')

        ordering = ['product', 'name']

        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['color']),
            models.Index(fields=['internal_code']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):

        return f"{self.product.name} - {self.name}"