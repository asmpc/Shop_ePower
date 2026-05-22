from django.db.models import Min
from django.db.models import Sum

from shop_epower.catalog.models import Product
from shop_epower.suppliers.models import SupplierProduct


def get_active_supplier_products(product: Product):
    """
    Returns active supplier products for product.
    """

    return SupplierProduct.objects.filter(
        product=product,
        is_active=True,
        supplier__is_active=True,
    )


def get_product_total_stock(product: Product) -> int:
    """
    Returns total stock across all active supplier products.
    """

    result = (
        get_active_supplier_products(product)
        .aggregate(
            total_stock=Sum("stock_quantity")
        )
    )

    return result["total_stock"] or 0


def is_product_in_stock(product: Product) -> bool:
    """
    Returns stock availability status.
    """

    return get_product_total_stock(product) > 0


def get_product_inventory_data(product: Product) -> dict:
    """
    Returns aggregated inventory information.
    """

    queryset = get_active_supplier_products(product)

    aggregated = queryset.aggregate(
        total_stock=Sum("stock_quantity"),
        min_lead_time=Min("lead_time_days"),
    )

    total_stock = aggregated["total_stock"] or 0

    return {
        "total_stock": total_stock,
        "in_stock": total_stock > 0,
        "supplier_count": queryset.count(),
        "min_lead_time": aggregated["min_lead_time"],
    }