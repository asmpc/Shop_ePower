from django import template
from decimal import Decimal
from shop_epower.suppliers.services.currency import CurrencyService

register = template.Library()

@register.filter
def convert_currency(value, target_currency):
    try:
        return CurrencyService.convert(Decimal(value), 'BYN', target_currency)
    except:
        return value