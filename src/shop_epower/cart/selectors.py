from shop_epower.cart.models import Cart


def get_cart_with_items(cart):
    return (
        Cart.objects
        .filter(id=cart.id)
        .prefetch_related(
            "items",
            "items__product",
            "items__product__images",
        )
        .first()
    )

def get_cart_totals(cart):
    items = cart.items.all()

    total = sum(
        item.total_price
        for item in items
    )

    total_quantity = sum(
        item.quantity
        for item in items
    )

    return {
        "total_price": total,
        "total_quantity": total_quantity,
    }