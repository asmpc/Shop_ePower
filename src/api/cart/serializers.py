from rest_framework import serializers
from shop_epower.catalog.models import Product



class CartItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(
        source="product.id",
    )
    product_name = serializers.CharField(
        source="product.name",
    )
    product_slug = serializers.CharField(
        source="product.slug",
    )
    quantity = serializers.IntegerField()
    price_snapshot = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    currency_snapshot = serializers.CharField()
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )


class CartSerializer(serializers.Serializer):
    items = CartItemSerializer(
        many=True,
    )
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    total_quantity = serializers.IntegerField()


class CartAddItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
    )
    quantity = serializers.IntegerField(
        min_value=1,
    )


class CartRemoveItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
    )
    quantity = serializers.IntegerField(
        required=False,
        min_value=1,
    )