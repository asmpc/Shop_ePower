from django.core.exceptions import ValidationError

from shop_epower.cart.models import Cart, CartItem


from shop_epower.suppliers.services.stock import get_product_inventory_public



def get_or_create_cart(user=None, session_key=""):
    if user and user.is_authenticated:
        cart, created = Cart.objects.get_or_create(
            user=user,
            is_active=True,
            defaults={
                "session_key": "",
            },
        )
        return cart

    cart, created = Cart.objects.get_or_create(
        session_key=session_key,
        is_active=True,
        user=None,
    )

    return cart


def add_product_to_cart(cart, product, quantity=1, user=None):
    if quantity <= 0:
        raise ValidationError(
            "Quantity must be greater than zero."
        )

    inventory = get_product_inventory_public(product)
    available_quantity = inventory.get("total_available", 0)

    existing_quantity = 0

    try:
        existing_item = CartItem.objects.get(
            cart=cart,
            product=product,
        )
        existing_quantity = existing_item.quantity
    except CartItem.DoesNotExist:
        pass

    requested_quantity = existing_quantity + quantity

    if requested_quantity > available_quantity:
        raise ValidationError(
            "Requested quantity exceeds available stock."
        )

    price = product.get_price_for_user(user)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={
            "quantity": quantity,
            "price_snapshot": price,
            "currency_snapshot": "BYN",
        },
    )

    if not created:
        item.quantity += quantity
        item.save(
            update_fields=[
                "quantity",
                "updated_at",
            ]
        )

    return item

def remove_product_from_cart(cart, product, quantity=None):
    try:
        item = CartItem.objects.get(
            cart=cart,
            product=product,
        )
    except CartItem.DoesNotExist:
        return

    if quantity is None:
        item.delete()
        return

    if quantity >= item.quantity:
        item.delete()
        return

    item.quantity -= quantity
    item.save(
        update_fields=[
            "quantity",
            "updated_at",
        ]
    )

    return item

def clear_cart(cart):
    cart.items.all().delete()