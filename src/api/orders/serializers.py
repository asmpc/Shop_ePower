from decimal import Decimal

from rest_framework import serializers

from shop_epower.orders.models import Order, OrderItem, OrderStatus
from shop_epower.payments.choices import PaymentMethod


class CheckoutSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        required=False,
    )

    def validate_payment_method(self, value):
        if value == PaymentMethod.ONLINE:
            raise serializers.ValidationError(
                "Online payment integration is currently unavailable."
            )

        return value


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


class OrderFundAssignmentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    operation_key = serializers.CharField(
        max_length=255,
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class OrderFundAssignmentCancelSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=True,
        allow_blank=False,
    )
    operation_key = serializers.CharField(
        max_length=255,
    )