from shop_epower.accounts.services.roles import is_manager

from shop_epower.suppliers.services.stock import (
    get_product_inventory_public,
    get_supplier_inventory_details,
)

from shop_epower.suppliers.services.cost import get_product_cost_summary



def prepare_product_for_user(product, user):
    product.final_price = product.get_price_for_user(user)
    product.inventory = get_product_inventory_public(product)

    if is_manager(user):
        product.supplier_inventory_details = get_supplier_inventory_details(product)
        product.cost_summary = get_product_cost_summary(product)

    return product