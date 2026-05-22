from django.contrib import admin

from shop_epower.suppliers.models import SupplierProduct


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "product",
        "supplier_article",
        "supplier_price",
        "stock_quantity",
        "lead_time_days",
        "is_active",
    )

    list_filter = (
        "supplier",
        "is_active",
    )

    search_fields = (
        "product__name",
        "supplier__name",
        "supplier_article",
    )

    autocomplete_fields = (
        "supplier",
        "product",
    )

    list_editable = (
        "supplier_price",
        "stock_quantity",
        "lead_time_days",
        "is_active",
    )