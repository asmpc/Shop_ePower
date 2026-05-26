from django.contrib import admin

from shop_epower.catalog.models import ProductVariantGroup



@admin.register(ProductVariantGroup)
class ProductVariantGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "variant_type",
        "products_count",
        "is_active",
    )

    list_filter = (
        "variant_type",
        "is_active",
    )

    search_fields = (
        "name",
        "products__name",
        "products__manufacturer_article",
    )

    filter_horizontal = (
        "products",
    )

    readonly_fields = (
        "products_count",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "variant_type",
                    "is_active",
                )
            },
        ),
        (
            "Products in this variant group",
            {
                "fields": (
                    "products",
                    "products_count",
                )
            },
        ),
    )

    def products_count(self, obj):
        if not obj.pk:
            return 0

        return obj.products.count()

    products_count.short_description = "Products count"