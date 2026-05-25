from django.contrib import admin
from django.contrib import messages

from shop_epower.catalog.models import Product
from shop_epower.suppliers.models import CategoryMarkup
from shop_epower.suppliers.services.currency import CurrencyService


@admin.register(CategoryMarkup)
class CategoryMarkupAdmin(admin.ModelAdmin):
    list_display = (
        "category",
        "percent",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "category__name",
    )

    autocomplete_fields = (
        "category",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    actions = (
        "recalculate_base_prices",
    )

    def recalculate_products_for_category(self, category):
        categories = [category] + self.get_descendant_categories(category)

        products = Product.objects.filter(
            category__in=categories,
            is_active=True,
        )

        updated_count = 0

        for product in products:
            CurrencyService.update_product_base_price(product)
            updated_count += 1

        return updated_count

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        updated_count = self.recalculate_products_for_category(obj.category)

        self.message_user(
            request,
            f"Base prices recalculated for {updated_count} products in category '{obj.category}'.",
            level=messages.SUCCESS,
        )

    def delete_model(self, request, obj):
        category = obj.category

        super().delete_model(request, obj)

        updated_count = self.recalculate_products_for_category(category)

        self.message_user(
            request,
            f"Category markup deleted. Base prices recalculated for {updated_count} products using global markup.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Recalculate base prices for selected category markups")
    def recalculate_base_prices(self, request, queryset):
        total_updated = 0

        for category_markup in queryset:
            total_updated += self.recalculate_products_for_category(
                category_markup.category
            )

        self.message_user(
            request,
            f"Base prices recalculated for {total_updated} products.",
            level=messages.SUCCESS,
        )

    def get_descendant_categories(self, category):
        descendants = []

        children = category.children.all()

        for child in children:
            descendants.append(child)
            descendants.extend(self.get_descendant_categories(child))

        return descendants

