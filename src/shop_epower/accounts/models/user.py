from django.contrib.auth.models import AbstractUser
from django.db import models
from .price_category import PriceCategory

class Role(models.TextChoices):
    CLIENT = 'client', 'Client'
    MANAGER = 'manager', 'Manager'
    ADMIN = 'admin', 'Admin'

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    price_category = models.ForeignKey(
        PriceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email