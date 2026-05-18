from django.contrib.auth.models import AbstractUser
from django.db import models


class PriceCategory(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    def __str__(self):
        return self.name


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
        blank=True
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email