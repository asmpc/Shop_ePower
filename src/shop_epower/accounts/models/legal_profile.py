from django.db import models

from .user import User


class LegalProfileType(models.TextChoices):
    LEGAL_ENTITY = 'legal_entity', 'Legal entity'
    INDIVIDUAL_ENTREPRENEUR = 'individual_entrepreneur', 'Individual entrepreneur'

class LegalProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='legal_profile')
    is_legal_entity = models.BooleanField(default=False, verbose_name='Represents a legal entity / sole proprietor')
    company_name = models.CharField(max_length=255, blank=True, verbose_name='Company name')
    tax_id = models.CharField(max_length=20, blank=True, verbose_name='Tax ID (UNP / INN)')
    legal_address = models.TextField(blank=True, verbose_name='Legal address')
    bank_name = models.CharField(max_length=255, blank=True, verbose_name='Bank')
    bank_account = models.CharField(max_length=50, blank=True, verbose_name='Bank account')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Legal profile'
        verbose_name_plural = 'Legal profiles'

    def __str__(self):
        return self.company_name or f'Legal profile for {self.user.email}'