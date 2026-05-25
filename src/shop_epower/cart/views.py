from django.views.generic import TemplateView

from shop_epower.cart.selectors import (
    get_cart_totals,
    get_cart_with_items,
)

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from shop_epower.catalog.models import Product
from shop_epower.cart.services import (
    add_product_to_cart,
    get_or_create_cart,
    remove_product_from_cart,
    clear_cart,
)




class CartDetailView(TemplateView):
    template_name = "cart/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not self.request.session.session_key:
            self.request.session.create()

        cart = get_or_create_cart(
            user=self.request.user,
            session_key=self.request.session.session_key,
        )

        cart = get_cart_with_items(cart)
        totals = get_cart_totals(cart)

        context["cart"] = cart
        context["cart_items"] = cart.items.all()
        context["cart_total_price"] = totals["total_price"]
        context["cart_total_quantity"] = totals["total_quantity"]

        return context


class CartAddView(View):

    def post(self, request, product_id):
        if not request.session.session_key:
            request.session.create()

        cart = get_or_create_cart(
            user=request.user,
            session_key=request.session.session_key,
        )

        product = get_object_or_404(
            Product,
            id=product_id,
            is_active=True,
        )

        quantity = int(
            request.POST.get("quantity", 1)
        )

        try:
            add_product_to_cart(
                cart=cart,
                product=product,
                quantity=quantity,
                user=request.user,
            )
            messages.success(
                request,
                "Product added to cart.",
            )
        except ValidationError as exc:
            messages.error(
                request,
                exc.messages[0],
                extra_tags="danger",
            )

        return redirect(
            request.META.get(
                "HTTP_REFERER",
                "cart-detail",
            )
        )

class CartRemoveView(View):

    def post(self, request, product_id):
        if not request.session.session_key:
            request.session.create()

        cart = get_or_create_cart(
            user=request.user,
            session_key=request.session.session_key,
        )

        product = get_object_or_404(
            Product,
            id=product_id,
        )

        quantity = request.POST.get("quantity")

        if quantity:
            quantity = int(quantity)

        remove_product_from_cart(
            cart=cart,
            product=product,
            quantity=quantity,
        )

        messages.success(
            request,
            "Product removed from cart.",
        )

        return redirect("cart-detail")

class CartClearView(View):

    def post(self, request):
        if not request.session.session_key:
            request.session.create()

        cart = get_or_create_cart(
            user=request.user,
            session_key=request.session.session_key,
        )

        clear_cart(cart)

        messages.success(
            request,
            "Cart cleared.",
        )

        return redirect("cart-detail")