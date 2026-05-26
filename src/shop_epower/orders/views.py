from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from shop_epower.cart.models import Cart
from shop_epower.orders.services import create_order_from_cart


@login_required
def checkout_view(request):
    if request.method != "POST":
        return redirect("cart-detail")

    try:
        cart = Cart.objects.get(
            user=request.user,
            is_active=True,
        )
    except Cart.DoesNotExist:
        messages.error(request, "Cart not found")
        return redirect("cart-detail")

    try:
        order = create_order_from_cart(
            user=request.user,
            cart=cart,
        )
    except Exception as e:
        messages.error(request, str(e))
        return redirect("cart-detail")

    return redirect("orders:success", order_id=order.id)

def order_success_view(request, order_id):
    return render(
        request,
        "orders/success.html",
        {"order_id": order_id}
    )