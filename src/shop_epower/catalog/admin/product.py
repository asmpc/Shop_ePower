from django.contrib import admin

from shop_epower.catalog.models import Product
from .variant_inline import ProductVariantInline
from .image_inline import ProductImageInline


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

    actions = ['deactivate_products']

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Deactivate selected products")
    def deactivate_products(self, request, queryset):
        queryset.update(is_active=False)