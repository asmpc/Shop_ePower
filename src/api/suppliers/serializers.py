from rest_framework import serializers

from shop_epower.suppliers.models import Supplier, SupplierProduct


class SupplierSerializer(serializers.ModelSerializer):

    class Meta:
        model = Supplier

        fields = (
            "id",
            "name",
            "is_own",
            "is_active",
        )


class SupplierProductSerializer(serializers.ModelSerializer):

    supplier_name = serializers.CharField(
        source="supplier.name",
        read_only=True,
    )

    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    class Meta:
        model = SupplierProduct

        fields = (
            "id",
            "supplier",
            "supplier_name",
            "product",
            "product_name",
            "supplier_article",
            "stock_quantity",
            "lead_time_days",
            "is_active",
        )