from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product_name",
        "unit_price",
        "quantity",
        "total_price",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_email",
        "status",
        "is_legal_entity",
        "total_price",
        "created_at",
    )

    list_filter = (
        "status",
        "is_legal_entity",
        "created_at",
    )

    search_fields = (
        "customer_email",
        "customer_name",
        "company_name",
        "tax_id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = (
        OrderItemInline,
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "product_name",
        "quantity",
        "unit_price",
        "total_price",
    )

    search_fields = (
        "product_name",
    )
