from django.contrib import admin

from shop_epower.suppliers.models import SupplierProduct
from shop_epower.suppliers.models import Supplier


class SupplierProductInline(admin.TabularInline):
    model = SupplierProduct

    extra = 1

    autocomplete_fields = (
        "product",
    )


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "phone",
        "website",
        "is_active",
        "is_own",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "email",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    inlines = [
        SupplierProductInline,
    ]