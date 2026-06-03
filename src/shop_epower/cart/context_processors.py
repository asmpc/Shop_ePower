from decimal import Decimal


def cart_summary(request):
    from shop_epower.cart.selectors import (
        get_cart_totals,
        get_cart_with_items,
    )
    from shop_epower.cart.services import get_or_create_cart

    if not hasattr(request, "session"):
        return {
            "navbar_cart_total_quantity": 0,
            "navbar_cart_total_price": Decimal("0.00"),
        }

    if not request.session.session_key:
        return {
            "navbar_cart_total_quantity": 0,
            "navbar_cart_total_price": Decimal("0.00"),
        }

    cart = get_or_create_cart(
        user=request.user,
        session_key=request.session.session_key,
    )

    cart = get_cart_with_items(cart)
    totals = get_cart_totals(cart)

    return {
        "navbar_cart_total_quantity": totals["total_quantity"],
        "navbar_cart_total_price": totals["total_price"],
    }

def chat_unread_summary(request):
    from shop_epower.chat.selectors import (
        get_unread_chat_messages_count_for_user,
    )

    if not request.user.is_authenticated:
        return {
            "navbar_unread_chat_messages_count": 0,
        }

    return {
        "navbar_unread_chat_messages_count": (
            get_unread_chat_messages_count_for_user(request.user)
        ),
    }

def new_orders_summary(request):
    from shop_epower.orders.selectors import (
        get_new_orders_count_for_manager,
    )

    if not request.user.is_authenticated:
        return {
            "navbar_new_orders_count": 0,
        }

    if request.user.role not in ("manager", "admin"):
        return {
            "navbar_new_orders_count": 0,
        }

    return {
        "navbar_new_orders_count": get_new_orders_count_for_manager(),
    }