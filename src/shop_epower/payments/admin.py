from django.contrib import admin

from shop_epower.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "method",
        "status",
        "provider",
        "amount",
        "currency_snapshot",
        "created_at",
    )

    list_filter = (
        "method",
        "status",
        "provider",
        "created_at",
    )

    search_fields = (
        "transaction_id",
        "provider_payment_id",
        "order__id",
        "order__customer_email",
    )

    readonly_fields = (
        "order",
        "method",
        "provider",
        "amount",
        "currency_snapshot",
        "transaction_id",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )