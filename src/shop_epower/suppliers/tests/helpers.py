from shop_epower.suppliers.models import (
    Supplier,
    SupplierProduct,
)


def create_test_supplier(
    *,
    name="Own Warehouse",
    is_own=True,
    is_active=True,
    **kwargs,
):
    return Supplier.objects.create(
        name=name,
        is_own=is_own,
        is_active=is_active,
        **kwargs,
    )


def create_test_supplier_product(
    *,
    supplier,
    product,
    supplier_article="SUP-TEST-001",
    stock_quantity=10,
    lead_time_days=0,
    is_active=True,
    **kwargs,
):
    return SupplierProduct.objects.create(
        supplier=supplier,
        product=product,
        supplier_article=supplier_article,
        stock_quantity=stock_quantity,
        lead_time_days=lead_time_days,
        is_active=is_active,
        **kwargs,
    )