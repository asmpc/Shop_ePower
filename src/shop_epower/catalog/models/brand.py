from django.db import models
from django.utils.translation import gettext_lazy as _

from shop_epower.core.models import BaseModel
from shop_epower.core.utils.slugs import generate_unique_slug


class Brand(BaseModel):

    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('Name')
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        verbose_name=_('Slug')
    )

    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )

    logo = models.ImageField(
        upload_to='brands/',
        blank=True,
        null=True,
        verbose_name=_('Logo')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is active')
    )

    class Meta:

        verbose_name = _('Brand')
        verbose_name_plural = _('Brands')

        ordering = ['name']

        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]

    def save(self, *args, **kwargs):

        if not self.slug:

            self.slug = generate_unique_slug(
                self,
                self.name
            )

        super().save(*args, **kwargs)

    def __str__(self):

        return self.name