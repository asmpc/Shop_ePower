from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.contrib.auth.views import redirect_to_login

from shop_epower.accounts.navigation import get_profile_edit_url
from shop_epower.cart.models import Cart
from shop_epower.orders.services import create_order_from_cart
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from shop_epower.orders.models import Order, OrderStatus
from shop_epower.orders.services import cancel_new_order
from shop_epower.chat.selectors import get_chat_rooms_for_order
from django.core.exceptions import ValidationError

from shop_epower.payments.services import (
    create_payment_for_order,
    validate_payment_method_for_delivery,
)
from shop_epower.payments.models import PaymentMethod

from shop_epower.accounts.services.profile import (
    is_profile_complete,
)

from django.urls import reverse


def checkout_view(request):

    if not request.user.is_authenticated:
        return redirect_to_login(
            reverse(
                "cart-detail",
            ),
            login_url=reverse(
                "accounts:login",
            ),
        )

    if request.method != "POST":
        return redirect("cart-detail")

    if request.method != "POST":
        return redirect("cart-detail")

    if not is_profile_complete(request.user):
        messages.error(
            request,
            "Complete your profile before placing an order.",
        )

        return redirect(
            get_profile_edit_url(
                next_url=reverse("cart-detail"),
            )
        )

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

    payment_method = request.POST.get(
        "payment_method",
        PaymentMethod.ON_RECEIPT,
    )

    # временно, пока не реализована оплата онлайн
    if payment_method == PaymentMethod.ONLINE:
        messages.error(
            request,
            "Online payment integration is currently under approval. "
            "At the moment you can pay by invoice or on receipt.",
        )

        return redirect("cart-detail")

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

    order_comment = request.POST.get(
        "order_comment",
        "",
    )

    try:
        validate_payment_method_for_delivery(
            delivery_method=delivery_method,
            payment_method=payment_method,
        )

        order = create_order_from_cart(
            user=request.user,
            cart=cart,
            delivery_method=delivery_method,
            delivery_provider=delivery_provider,
            delivery_address=delivery_address,
            delivery_comment=delivery_comment,
            order_comment=order_comment,
        )

        create_payment_for_order(
            order=order,
            method=payment_method,
        )

    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("cart-detail")

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

    status = request.GET.get("status")

    if status and status != "all":
        orders = orders.filter(status=status)

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
        Order.objects.select_related("payment"),
        id=order_id,
        user=request.user,
    )

    chat_rooms = get_chat_rooms_for_order(order)

    try:
        payment = order.payment
    except Order.payment.RelatedObjectDoesNotExist:
        payment = None

    return render(
        request,
        "orders/detail.html",
        {
            "order": order,
            "payment": payment,
            "can_cancel": order.status == OrderStatus.NEW,
            "chat_rooms": chat_rooms,
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