from shop_epower.suppliers.services.currency import CurrencyService
from shop_epower.catalog.models import Product

from django.contrib import admin

from shop_epower.core.currency import get_base_currency
from shop_epower.suppliers.models import CurrencyRate


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = (
        "currency",
        "rate_to_base_currency",
        "base_currency",
        "updated_at",
    )

    readonly_fields = (
        "base_currency",
        "updated_at",
    )

    fields = (
        "currency",
        "base_currency",
        "rate_to_base_currency",
        "updated_at",
    )

    def base_currency(self, obj):
        return get_base_currency()

    base_currency.short_description = "Base currency"

    @admin.action(description="Recalculate base price for all products using current currency rates")
    def recalculate_all_products(self, request, queryset):
        products = Product.objects.all()
        for product in products:
            CurrencyService.update_product_base_price(product)
        self.message_user(request, f"Base prices recalculated for {products.count()} products")