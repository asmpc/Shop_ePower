from shop_epower.catalog.models import Product
from shop_epower.suppliers.services.currency import CurrencyService


def recalc_product_base_price(product: Product):
    """
    Пересчитывает Product.base_price через единый currency/pricing service.

    Важно:
    - учитывает валюту поставщика
    - конвертирует цену в базовую валюту проекта
    - применяет category/global markup
    """
    return CurrencyService.update_product_base_price(product)