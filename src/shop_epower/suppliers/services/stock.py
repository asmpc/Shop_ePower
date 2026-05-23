from django.db.models import Sum, Min
from shop_epower.catalog.models import Product
from shop_epower.suppliers.models import SupplierProduct, Supplier


def get_product_inventory_detailed(product: Product) -> dict:
    """
    Returns inventory breakdown:
    - own stock (our warehouse)
    - supplier stock (external suppliers)
    - total
    - min lead time (only external suppliers)
    """
    own_stock_qs = SupplierProduct.objects.filter(
        product=product,
        is_active=True,
        supplier__is_active=True,
        supplier__is_own=True
    )

    supplier_stock_qs = SupplierProduct.objects.filter(
        product=product,
        is_active=True,
        supplier__is_active=True,
        supplier__is_own=False
    )

    own_stock = own_stock_qs.aggregate(total=Sum("stock_quantity"))["total"] or 0
    supplier_stock_agg = supplier_stock_qs.aggregate(
        total=Sum("stock_quantity"),
        min_lead_time=Min("lead_time_days")
    )
    supplier_stock = supplier_stock_agg["total"] or 0
    min_lead_time = supplier_stock_agg["min_lead_time"]

    total_stock = own_stock + supplier_stock
    in_stock = total_stock > 0

    return {
        "own_stock": own_stock,
        "supplier_stock": supplier_stock,
        "total_stock": total_stock,
        "min_lead_time": min_lead_time,
        "in_stock": in_stock,
    }


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


def get_supplier_inventory_details(product: Product):
    """
    Returns supplier-level inventory details for manager/admin visibility.
    """

    return get_active_supplier_products(product).select_related(
        "supplier",
    )