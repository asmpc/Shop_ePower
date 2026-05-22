from django.contrib import admin
from shop_epower.suppliers.models import SupplierProduct
from shop_epower.suppliers.services.pricing import recalc_product_base_price


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

    actions = ['recalculate_base_price']  # добавляем action

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        recalc_product_base_price(obj.product)

    @admin.action(description="Recalculate base price for selected SupplierProducts")
    def recalculate_base_price(self, request, queryset):
        # Берем уникальные продукты из выбранных SupplierProduct
        products = {sp.product for sp in queryset}
        for product in products:
            recalc_product_base_price(product)
        self.message_user(request, f"Base prices recalculated for {len(products)} products")