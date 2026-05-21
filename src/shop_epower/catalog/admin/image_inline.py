from django.contrib import admin
from shop_epower.catalog.models import ProductImage


class ProductImageInline(admin.TabularInline):

    model = ProductImage
    extra = 1

    fields = (
        'image',
        'alt_text',
        'is_primary',
        'sort_order',
        'variant',
    )

    ordering = (
        'sort_order',
    )