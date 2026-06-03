from rest_framework import serializers

from shop_epower.orders.models import Order, OrderItem, OrderStatus


class CheckoutSerializer(serializers.Serializer):
    pass


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_name",
            "unit_price",
            "quantity",
            "total_price",
        )


class OrderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "is_legal_entity",
            "total_price",
            "created_at",
        )


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "is_legal_entity",
            "customer_name",
            "customer_email",
            "customer_phone",
            "company_name",
            "tax_id",
            "legal_address",
            "bank_name",
            "bank_account",
            "total_price",
            "created_at",
            "items",
        )

class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=OrderStatus.choices,
    )

    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    cancellation_comment = serializers.CharField(
        required=False,
        allow_blank=True,
    )