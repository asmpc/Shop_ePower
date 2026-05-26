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


class LegalProfileType(models.TextChoices):
    LEGAL_ENTITY = 'legal_entity', 'Legal entity'
    INDIVIDUAL_ENTREPRENEUR = 'individual_entrepreneur', 'Individual entrepreneur'


class LegalProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='legal_profile',
    )

    is_legal_entity = models.BooleanField(
        default=False,
        verbose_name='Represents a legal entity / sole proprietor',
    )

    company_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Company name',
    )

    tax_id = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Tax ID (UNP / INN)',
    )

    legal_address = models.TextField(
        blank=True,
        verbose_name='Legal address',
    )

    bank_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Bank',
    )

    bank_account = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Bank account',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )


    class Meta:
        verbose_name = 'Legal profile'
        verbose_name_plural = 'Legal profiles'

    def __str__(self):
        return self.company_name or f'Legal profile for {self.user.email}'
