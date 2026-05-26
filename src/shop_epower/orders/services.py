from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from shop_epower.orders.models import Order, OrderItem
from shop_epower.suppliers.models import SupplierProduct



@transaction.atomic
def create_order_from_cart(*, user, cart):
    if not user or not user.is_authenticated:
        raise ValidationError("User must be authenticated.")

    if cart.user_id != user.id:
        raise ValidationError("Cart does not belong to user.")

    cart_items = list(
        cart.items.select_related("product")
    )

    if not cart_items:
        raise ValidationError("Cart is empty.")

    for cart_item in cart_items:
        reserve_stock_for_order_item(
            product=cart_item.product,
            quantity=cart_item.quantity,
        )

    legal_profile = getattr(user, "legal_profile", None)

    is_legal_entity = (
        legal_profile is not None
        and legal_profile.is_legal_entity
    )

    total_price = sum(
        item.total_price for item in cart_items
    )

    order = Order.objects.create(
        user=user,
        is_legal_entity=is_legal_entity,
        customer_name=user.get_full_name() or user.username,
        customer_email=user.email,
        customer_phone=getattr(user, "phone", ""),
        company_name=legal_profile.company_name if is_legal_entity else "",
        tax_id=legal_profile.tax_id if is_legal_entity else "",
        legal_address=legal_profile.legal_address if is_legal_entity else "",
        bank_name=legal_profile.bank_name if is_legal_entity else "",
        bank_account=legal_profile.bank_account if is_legal_entity else "",
        total_price=total_price or Decimal("0.00"),
    )

    order_items = [
        OrderItem(
            order=order,
            product=cart_item.product,
            product_name=cart_item.product.name,
            unit_price=cart_item.price_snapshot,
            quantity=cart_item.quantity,
            total_price=cart_item.total_price,
        )
        for cart_item in cart_items
    ]

    OrderItem.objects.bulk_create(order_items)

    cart.is_active = False
    cart.save(update_fields=["is_active"])

    return order

def reserve_stock_for_order_item(*, product, quantity):
    supplier_products = (
        SupplierProduct.objects
        .select_for_update()
        .filter(
            product=product,
            is_active=True,
            supplier__is_active=True,
            stock_quantity__gt=0,
        )
        .order_by(
            "-supplier__is_own",
            "lead_time_days",
            "id",
        )
    )

    total_stock = sum(
        supplier_product.stock_quantity
        for supplier_product in supplier_products
    )

    if total_stock < quantity:
        raise ValidationError(
            f"Not enough stock for product: {product.name}"
        )

    remaining_quantity = quantity

    for supplier_product in supplier_products:
        if remaining_quantity <= 0:
            break

        quantity_to_reserve = min(
            supplier_product.stock_quantity,
            remaining_quantity,
        )

        supplier_product.stock_quantity -= quantity_to_reserve
        supplier_product.save(
            update_fields=["stock_quantity"]
        )

        remaining_quantity -= quantity_to_reserve