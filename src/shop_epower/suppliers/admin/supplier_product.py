from django.contrib import admin

from shop_epower.core.currency import get_base_currency
from shop_epower.suppliers.models import SupplierProduct
from shop_epower.suppliers.services.currency import CurrencyService
from shop_epower.suppliers.models import CurrencyRate
from django.contrib import messages
from unittest.mock import patch




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

    actions = ['recalc_base_price_action']

    def save_model(self, request, obj, form, change):
        # Проверяем, что для выбранной валюты задан курс
        if obj.currency != get_base_currency():
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

    # Проверяем, что admin action пересчитывает каждый Product только один раз,
    # даже если в queryset есть несколько SupplierProduct для одного товара.
    def test_admin_action_recalculates_each_product_only_once(self):
        second_supplier_product = SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product1,
            supplier_article="A1-SECOND",
            supplier_price=200,
            stock_quantity=2,
        )

        request = self.factory.get("/")

        queryset = SupplierProduct.objects.filter(
            id__in=[
                self.sp1.id,
                second_supplier_product.id,
            ]
        )

        with patch(
                "shop_epower.suppliers.admin.supplier_product.CurrencyService.update_product_base_price"
        ) as mocked_update:
            self.admin.recalc_base_price_action(
                request,
                queryset,
            )

        mocked_update.assert_called_once_with(self.product1)