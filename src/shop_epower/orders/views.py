from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from shop_epower.cart.models import Cart
from shop_epower.orders.services import create_order_from_cart
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from shop_epower.orders.models import Order, OrderStatus
from shop_epower.orders.services import cancel_new_order


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

    delivery_method = request.POST.get(
        "delivery_method",
        "pickup",
    )

    delivery_provider = request.POST.get(
        "delivery_provider",
        "",
    )

    delivery_address = request.POST.get(
        "delivery_address",
        "",
    )

    delivery_comment = request.POST.get(
        "delivery_comment",
        "",
    )

    try:
        order = create_order_from_cart(
            user=request.user,
            cart=cart,
            delivery_method=delivery_method,
            delivery_provider=delivery_provider,
            delivery_address=delivery_address,
            delivery_comment=delivery_comment,
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

@login_required
def order_list_view(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )

    return render(
        request,
        "orders/list.html",
        {
            "orders": orders,
        },
    )

@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"),
        id=order_id,
        user=request.user,
    )

    return render(
        request,
        "orders/detail.html",
        {
            "order": order,
            "can_cancel": order.status == OrderStatus.NEW,
        },
    )

@login_required
@require_POST
def order_cancel_view(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user,
    )

    try:
        cancel_new_order(
            order=order,
            user=request.user,
        )
    except Exception as e:
        messages.error(request, str(e))
        return redirect("orders:detail", order_id=order.id)

    messages.success(request, "Order cancelled successfully.")
    return redirect("orders:detail", order_id=order.id)