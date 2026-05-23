from django.db import models
from django.utils.translation import gettext_lazy as _

from shop_epower.core.models import BaseModel
from shop_epower.core.utils.slugs import generate_unique_slug


class Category(BaseModel):

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_('Parent category')
    )

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

    image = models.ImageField(
        upload_to='categories/',
        null=True,
        blank=True,
        verbose_name=_('Image')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is active')
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Sort order')
    )

    class Meta:

        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

        ordering = ['sort_order', 'name']

        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['parent']),
            models.Index(fields=['is_active']),
            models.Index(fields=['sort_order']),
        ]

    def save(self, *args, **kwargs):

        if not self.slug:
            self.slug = generate_unique_slug(self, self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name