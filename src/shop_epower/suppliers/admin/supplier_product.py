from django.contrib import admin
from shop_epower.suppliers.models import SupplierProduct
from shop_epower.suppliers.services.currency import CurrencyService
from shop_epower.suppliers.models import CurrencyRate
from django.contrib import messages



@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "product",
        "supplier_article",
        "supplier_price",
        "currency",
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
        "currency",
        "stock_quantity",
        "lead_time_days",
        "is_active",
    )

    actions = ['recalculate_base_price']  # добавляем action

    def save_model(self, request, obj, form, change):
        # Проверяем, что для выбранной валюты задан курс
        if obj.currency != "BYN":  # для BYN курс не нужен
            rate_exists = CurrencyRate.objects.filter(currency=obj.currency).exists()
            if not rate_exists:
                messages.error(
                    request,
                    f"Для валюты {obj.currency} курс не задан! Сначала создайте CurrencyRate."
                )
                return  # не сохраняем объект и не пересчитываем цену

        super().save_model(request, obj, form, change)

        # пересчет базовой цены после сохранения, если курс есть
        from shop_epower.suppliers.services.currency import CurrencyService
        CurrencyService.update_product_base_price(obj.product)

    @admin.action(description="Recalculate base price for selected SupplierProducts")
    def recalc_base_price_action(self, request, queryset):
        products = {sp.product for sp in queryset}
        for product in products:
            CurrencyService.update_product_base_price(product)
        self.message_user(request, f"Base prices recalculated for {len(products)} products")