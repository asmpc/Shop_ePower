from rest_framework import serializers

from shop_epower.catalog.models import Product



class ProductImageSerializer(serializers.Serializer):
    image = serializers.ImageField()
    alt_text = serializers.CharField()
    is_primary = serializers.BooleanField()
    sort_order = serializers.IntegerField()


class ProductListSerializer(serializers.ModelSerializer):
    final_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    inventory = serializers.DictField(
        read_only=True,
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "final_price",
            "inventory",
        ]

class ProductDetailSerializer(ProductListSerializer):

    brand = serializers.CharField(source="brand.name")
    category = serializers.CharField(source="category.name")
    description = serializers.CharField()
    manufacturer_article = serializers.CharField()

    images = ProductImageSerializer(
        many=True,
        read_only=True,
    )

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "brand",
            "category",
            "description",
            "manufacturer_article",
            "images",
            "supplier_inventory_details",
            "cost_summary",
        ]

    supplier_inventory_details = serializers.JSONField(required=False)
    cost_summary = serializers.JSONField(required=False)