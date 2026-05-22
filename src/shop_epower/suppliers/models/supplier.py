from django.db import models
from django.utils.text import slugify


class Supplier(models.Model):
    name = models.CharField(
        max_length=255,
        unique=True,
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    phone = models.CharField(
        max_length=50,
        blank=True,
    )

    website = models.URLField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    # Новое поле
    is_own = models.BooleanField(default=False)  # отмечает наш склад

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name