from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from shop_epower.cart.models import Cart
from shop_epower.orders.models import Order
from .serializers import (
    CheckoutSerializer,
    OrderListSerializer,
    OrderDetailSerializer,
    OrderStatusUpdateSerializer,
)
from shop_epower.orders.services import (
    create_order_from_cart,
    cancel_new_order,
    update_order_status_by_manager,
)



def is_manager_or_admin(user):
    return user.role in ("manager", "admin")

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

class ManagerOrderListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_manager_or_admin(request.user):
            return Response(
                {"detail": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN,
            )

        orders = (
            Order.objects
            .select_related("user")
            .order_by("-created_at")
        )

        serializer = OrderListSerializer(
            orders,
            many=True,
        )

        return Response(serializer.data)


class ManagerOrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        if not is_manager_or_admin(request.user):
            return Response(
                {"detail": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN,
            )

        order = get_object_or_404(
            Order.objects
            .select_related("user")
            .prefetch_related("items"),
            id=order_id,
        )

        serializer = OrderDetailSerializer(order)

        return Response(serializer.data)

@extend_schema(
    request=OrderStatusUpdateSerializer,
    responses=OrderDetailSerializer,
)
class ManagerOrderStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        if not is_manager_or_admin(request.user):
            return Response(
                {"detail": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OrderStatusUpdateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(
            Order,
            id=order_id,
        )

        try:
            update_order_status_by_manager(
                order=order,
                user=request.user,
                new_status=serializer.validated_data["status"],
            )
        except ValidationError as error:
            return Response(
                {"detail": error.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.refresh_from_db()

        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_200_OK,
        )