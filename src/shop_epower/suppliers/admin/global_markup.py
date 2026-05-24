from django.contrib import admin

from shop_epower.suppliers.models import GlobalMarkup


@admin.register(GlobalMarkup)
class GlobalMarkupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "percent",
        "updated_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )