import django_filters

from shop_epower.catalog.models import Product


class ProductFilter(django_filters.FilterSet):
    brand = django_filters.CharFilter(
        field_name="brand__slug",
        lookup_expr="exact",
    )

    category = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr="exact",
    )

    class Meta:
        model = Product
        fields = [
            "brand",
            "category",
        ]