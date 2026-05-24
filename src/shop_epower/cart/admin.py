from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = (
        "price_snapshot",
        "currency_snapshot",
        "total_price",
    )


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "session_key",
        "is_active",
        "created_at",
    )
    list_filter = (
        "is_active",
        "created_at",
    )
    search_fields = (
        "user__email",
        "session_key",
    )
    inlines = [
        CartItemInline,
    ]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cart",
        "product",
        "quantity",
        "price_snapshot",
        "currency_snapshot",
        "total_price",
    )
    search_fields = (
        "product__name",
        "cart__user__email",
        "cart__session_key",
    )
