from django.core.exceptions import ValidationError

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shop_epower.cart.models import Cart
from shop_epower.orders.services import create_order_from_cart

from django.shortcuts import get_object_or_404

from shop_epower.orders.models import Order
from shop_epower.orders.services import cancel_new_order
from .serializers import (
    CheckoutSerializer,
    OrderListSerializer,
    OrderDetailSerializer,
)



class CheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cart = Cart.objects.get(
                user=request.user,
                is_active=True,
            )
        except Cart.DoesNotExist:
            return Response(
                {"detail": "Active cart not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = create_order_from_cart(
                user=request.user,
                cart=cart,
            )
        except ValidationError as error:
            return Response(
                {"detail": error.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "order_id": order.id,
                "total_price": str(order.total_price),
            },
            status=status.HTTP_201_CREATED,
        )

class OrderListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects
            .filter(user=request.user)
            .order_by("-created_at")
        )

        serializer = OrderListSerializer(
            orders,
            many=True,
        )

        return Response(serializer.data)


class OrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.prefetch_related("items"),
            id=order_id,
            user=request.user,
        )

        serializer = OrderDetailSerializer(order)

        return Response(serializer.data)


class OrderCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
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
        except ValidationError as error:
            return Response(
                {"detail": error.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Order cancelled successfully."},
            status=status.HTTP_200_OK,
        )