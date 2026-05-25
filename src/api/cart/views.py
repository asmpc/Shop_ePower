from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from shop_epower.cart.selectors import (
    get_cart_totals,
    get_cart_with_items,
)

from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError


from .serializers import (
    CartSerializer,
    CartAddItemSerializer,
    CartRemoveItemSerializer,
)

from shop_epower.cart.services import (
    add_product_to_cart,
    clear_cart,
    get_or_create_cart,
    remove_product_from_cart,
)



class CartAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cart = get_or_create_cart(
            user=request.user,
            session_key=request.session.session_key or "",
        )

        cart = get_cart_with_items(cart)

        totals = get_cart_totals(cart)

        data = {
            "items": cart.items.all(),
            "total_price": totals["total_price"],
            "total_quantity": totals["total_quantity"],
        }

        serializer = CartSerializer(data)

        return Response(serializer.data)

class CartAddItemAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CartAddItemSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        if not request.session.session_key:
            request.session.create()

        cart = get_or_create_cart(
            user=request.user,
            session_key=request.session.session_key,
        )

        try:
            add_product_to_cart(
                cart=cart,
                product=serializer.validated_data["product"],
                quantity=serializer.validated_data["quantity"],
                user=request.user,
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)

        cart = get_cart_with_items(cart)
        totals = get_cart_totals(cart)

        response_data = {
            "items": cart.items.all(),
            "total_price": totals["total_price"],
            "total_quantity": totals["total_quantity"],
        }

        response_serializer = CartSerializer(
            response_data,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class CartRemoveItemAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CartRemoveItemSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        if not request.session.session_key:
            request.session.create()

        cart = get_or_create_cart(
            user=request.user,
            session_key=request.session.session_key,
        )

        remove_product_from_cart(
            cart=cart,
            product=serializer.validated_data["product"],
            quantity=serializer.validated_data.get("quantity"),
        )

        cart = get_cart_with_items(cart)
        totals = get_cart_totals(cart)

        response_data = {
            "items": cart.items.all(),
            "total_price": totals["total_price"],
            "total_quantity": totals["total_quantity"],
        }

        response_serializer = CartSerializer(response_data)

        return Response(response_serializer.data)


class CartClearAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not request.session.session_key:
            request.session.create()

        cart = get_or_create_cart(
            user=request.user,
            session_key=request.session.session_key,
        )

        clear_cart(cart)

        return Response(
            {
                "items": [],
                "total_price": "0.00",
                "total_quantity": 0,
            }
        )