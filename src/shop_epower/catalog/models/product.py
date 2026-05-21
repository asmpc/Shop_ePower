from django.db import models
from django.utils.translation import gettext_lazy as _

from shop_epower.core.models import BaseModel
from shop_epower.core.utils.slugs import generate_unique_slug

from decimal import Decimal



class Product(BaseModel):

    class UnitType(models.TextChoices):
        PIECE = 'piece', _('Piece')
        SET = 'set', _('Set')
        METER = 'meter', _('Meter')
        ROLL = 'roll', _('Roll')
        PACK = 'pack', _('Pack')

    name = models.CharField(
        max_length=255,
        verbose_name=_('Name')
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        verbose_name=_('Slug')
    )

    brand = models.ForeignKey(
        'catalog.Brand',
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name=_('Brand')
    )

    category = models.ForeignKey(
        'catalog.Category',
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name=_('Category')
    )

    manufacturer_article = models.CharField(
        max_length=255,
        verbose_name=_('Manufacturer article')
    )

    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Base price'),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )

    unit_type = models.CharField(
        max_length=20,
        choices=UnitType.choices,
        default=UnitType.PIECE,
        verbose_name=_('Unit type')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is active')
    )

    class Meta:

        verbose_name = _('Product')
        verbose_name_plural = _('Products')

        ordering = ['name']

        constraints = [
            models.UniqueConstraint(
                fields=['brand', 'manufacturer_article'],
                name='unique_brand_article'
            )
        ]

        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['brand']),
            models.Index(fields=['category']),
            models.Index(fields=['manufacturer_article']),
            models.Index(fields=['is_active']),
        ]

    def save(self, *args, **kwargs):

        if not self.slug:
            self.slug = generate_unique_slug(self, self.name)

        super().save(*args, **kwargs)

    def apply_discount(self, price, discount_percent):

        if not discount_percent:
            return price

        discount_multiplier = (
                                      Decimal('100') - Decimal(discount_percent)
                              ) / Decimal('100')

        return (price * discount_multiplier).quantize(
            Decimal('0.01')
        )

    def get_price_for_user(self, user):

        base_price = self.base_price

        if not user or not user.is_authenticated:
            return base_price

        if not user.price_category:
            return base_price

        discount = user.price_category.discount_percent

        return self.apply_discount(
            base_price,
            discount
        )

    def __str__(self):

        return self.name