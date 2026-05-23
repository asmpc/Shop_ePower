from django.contrib import admin
from shop_epower.suppliers.models import CurrencyRate
from shop_epower.suppliers.services.currency import CurrencyService
from shop_epower.catalog.models import Product

@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ("currency", "rate_to_BYN", "updated_at")
    readonly_fields = ("updated_at",)

    actions = ['recalculate_all_products']

    @admin.action(description="Recalculate base price for all products using current currency rates")
    def recalculate_all_products(self, request, queryset):
        products = Product.objects.all()
        for product in products:
            CurrencyService.update_product_base_price(product)
        self.message_user(request, f"Base prices recalculated for {products.count()} products")