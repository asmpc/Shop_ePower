from django.contrib import admin
from shop_epower.catalog.models import ProductVariant


class ProductVariantInline(admin.StackedInline):

    model = ProductVariant
    extra = 1

    fields = (
        'name',
        'color',
        'internal_code',
        'is_active',
    )

    readonly_fields = (
        'internal_code',
    )