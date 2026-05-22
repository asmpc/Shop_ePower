from django.db.models import Max
from shop_epower.catalog.models import Product
from shop_epower.suppliers.models import SupplierProduct, GlobalMarkup

def recalc_product_base_price(product: Product):
    """
    Пересчет Product.base_price на основе активных SupplierProduct
    с применением глобальной маржи.
    """
    active_suppliers = SupplierProduct.objects.filter(
        product=product,
        is_active=True,
        supplier__is_active=True,
    )

    if not active_suppliers.exists():
        return  # нет активных поставщиков

    max_supplier_price = active_suppliers.aggregate(
        max_price=Max("supplier_price")
    )["max_price"]

    if max_supplier_price is None:
        return

    # Берем глобальный процент наценки
    markup_obj = GlobalMarkup.objects.first()
    markup_percent = markup_obj.percent if markup_obj else 20  # дефолт 20%

    # Выставляем базовую цену
    product.base_price = max_supplier_price * (1 + markup_percent / 100)
    product.save(update_fields=["base_price"])