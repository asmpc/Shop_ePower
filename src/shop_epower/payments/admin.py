from django.contrib import admin

from shop_epower.payments.models import (
    Payment,
    PaymentHistory,
)


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

@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment",
        "old_status",
        "new_status",
        "changed_by",
        "created_at",
    )

    list_filter = (
        "old_status",
        "new_status",
        "created_at",
    )

    search_fields = (
        "payment__transaction_id",
        "payment__order__id",
        "payment__order__customer_email",
        "changed_by__username",
        "changed_by__email",
    )

    readonly_fields = (
        "payment",
        "old_status",
        "new_status",
        "comment",
        "changed_by",
        "created_at",
    )

    ordering = (
        "-created_at",
    )