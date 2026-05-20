# Models for accounts: user and pricecategory

from django.contrib.auth.models import AbstractUser
from django.db import models



class Role(models.TextChoices):
    CLIENT = 'client', 'Client'

    MANAGER = 'manager', 'Manager'

    ADMIN = 'admin', 'Admin'

class PriceCategory(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:

        ordering = ['id']

        verbose_name = 'Price category'

        verbose_name_plural = 'Price categories'

    def __str__(self):

        return (
            f'{self.name}'
            f' ({self.discount_percent}%)'
        )


class User(AbstractUser):

    email = models.EmailField(
        unique=True
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    price_category = models.ForeignKey(
        PriceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )


    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

