from django.contrib import admin

from shop_epower.catalog.models import Product
from .variant_inline import ProductVariantInline
from .image_inline import ProductImageInline
from shop_epower.suppliers.services.pricing import recalc_product_base_price


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'brand',
        'category',
        'manufacturer_article',
        'unit_type',
        'is_active',
        'created_at',
        'base_price',
    )

    list_filter = (
        'brand',
        'category',
        'unit_type',
        'is_active',
    )

    search_fields = (
        'name',
        'manufacturer_article',
        'slug',
    )

    prepopulated_fields = {
        'slug': ('name',)
    }

    ordering = ('name',)

    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Main info', {
            'fields': (
                'name',
                'slug',
                'brand',
                'category',
                'manufacturer_article',
                'unit_type',
                'description',
                'base_price',
                'is_active',
            )
        }),
        ('System info', {
            'fields': (
                'id',
                'created_at',
                'updated_at',
            )
        }),
    )

    inlines = [
        ProductVariantInline,
        ProductImageInline,
    ]

    actions = ['deactivate_products', 'recalculate_base_price']

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Deactivate selected products")
    def deactivate_products(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Recalculate base price for selected products")
    def recalculate_base_price(self, request, queryset):
        for product in queryset:
            recalc_product_base_price(product)
        self.message_user(request, f"Base prices recalculated for {queryset.count()} products")