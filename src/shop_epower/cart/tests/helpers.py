from decimal import Decimal

from shop_epower.cart.models import Cart, CartItem


def create_test_cart(
    *,
    user=None,
    session_key="",
    is_active=True,
    **kwargs,
):
    return Cart.objects.create(
        user=user,
        session_key=session_key,
        is_active=is_active,
        **kwargs,
    )


def create_test_cart_item(
    *,
    cart,
    product,
    quantity=1,
    price_snapshot=Decimal("10.00"),
    currency_snapshot="BYN",
    **kwargs,
):
    return CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=quantity,
        price_snapshot=price_snapshot,
        currency_snapshot=currency_snapshot,
        **kwargs,
    )


def create_test_cart_with_item(
    *,
    user,
    product,
    quantity=1,
    price_snapshot=Decimal("10.00"),
    currency_snapshot="BYN",
):
    cart = create_test_cart(
        user=user,
    )

    create_test_cart_item(
        cart=cart,
        product=product,
        quantity=quantity,
        price_snapshot=price_snapshot,
        currency_snapshot=currency_snapshot,
    )

    return cart