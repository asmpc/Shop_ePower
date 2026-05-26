from django.core.exceptions import ValidationError

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shop_epower.cart.models import Cart
from shop_epower.orders.services import create_order_from_cart

from .serializers import CheckoutSerializer


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