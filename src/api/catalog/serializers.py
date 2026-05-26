from rest_framework import serializers

from shop_epower.catalog.models import Product


class ProductImageSerializer(serializers.Serializer):
    image = serializers.ImageField()
    alt_text = serializers.CharField()
    is_primary = serializers.BooleanField()
    sort_order = serializers.IntegerField()


class ProductVariantSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    variant_type = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "image",
            "variant_type",
        ]

    def get_image(self, obj):
        image = obj.images.first()

        if not image:
            return None

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(image.image.url)

        return image.image.url


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

    variants = serializers.SerializerMethodField()

    supplier_inventory_details = serializers.JSONField(required=False)
    cost_summary = serializers.JSONField(required=False)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "brand",
            "category",
            "description",
            "manufacturer_article",
            "images",
            "variants",
            "supplier_inventory_details",
            "cost_summary",
        ]

    def get_variants(self, obj):
        variants = []

        variant_groups = obj.variant_groups.filter(is_active=True)

        for group in variant_groups:
            for product in group.products.exclude(id=obj.id):
                product.variant_type = group.variant_type
                variants.append(product)

        return ProductVariantSerializer(
            variants,
            many=True,
            context=self.context,
        ).data