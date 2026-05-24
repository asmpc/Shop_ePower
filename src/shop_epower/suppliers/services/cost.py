from decimal import Decimal, ROUND_HALF_UP

from shop_epower.suppliers.models import SupplierProduct
from shop_epower.suppliers.services.currency import CurrencyService
from shop_epower.suppliers.services.markup import get_markup_percent_for_product



def get_product_cost_summary(product) -> dict | None:
    """
    Internal manager/admin cost summary.

    Shows supplier cost analytics in BYN.
    Not for public/client visibility.
    """

    supplier_products = SupplierProduct.objects.filter(
        product=product,
        is_active=True,
        supplier__is_active=True,
    ).exclude(
        supplier_price__isnull=True,
    )

    if not supplier_products.exists():
        return None

    supplier_costs_byn = [
        CurrencyService.convert(
            amount=supplier_product.supplier_price,
            from_currency=supplier_product.currency,
            to_currency="BYN",
        )
        for supplier_product in supplier_products
    ]

    max_supplier_cost_byn = max(supplier_costs_byn)

    markup_percent = get_markup_percent_for_product(product)

    base_price = product.base_price or Decimal("0")

    margin_amount = (
        base_price - max_supplier_cost_byn
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    return {
        "max_supplier_cost_byn": max_supplier_cost_byn,
        "markup_percent": markup_percent,
        "base_price": base_price,
        "margin_amount": margin_amount,
    }