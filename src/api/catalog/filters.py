import django_filters

from shop_epower.catalog.models import (
    Product,
    Category,
)

from shop_epower.catalog.selectors.products import (
    get_category_with_descendants,
)



class ProductFilter(django_filters.FilterSet):
    brand = django_filters.CharFilter(
        field_name="brand__slug",
        lookup_expr="exact",
    )

    category = django_filters.CharFilter(
        method="filter_category",
    )

    def filter_category(self, queryset, name, value):
        try:
            category = Category.objects.get(
                slug=value,
            )
        except Category.DoesNotExist:
            return queryset.none()

        categories = get_category_with_descendants(
            category
        )

        return queryset.filter(
            category__in=categories
        )

    class Meta:
        model = Product
        fields = [
            "brand",
            "category",
        ]