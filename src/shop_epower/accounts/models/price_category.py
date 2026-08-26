from django.db import models


class PriceCategory(models.Model):

    name = models.CharField(max_length=100, unique=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Price category'
        verbose_name_plural = 'Price categories'

    def __str__(self):
        return f'{self.name} ({self.discount_percent}%)'