from django.contrib import admin

from shop_epower.payments.models import (
    CompanySettings,
    Invoice,
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


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):

    list_display = (
        "company_name",
        "short_company_name",
        "tax_id",
        "bank_name",
        "phone",
        "updated_at",
    )

    search_fields = (
        "company_name",
        "short_company_name",
        "tax_id",
        "email",
    )

    fieldsets = (
        (
            "Company information",
            {
                "fields": (
                    "company_name",
                    "short_company_name",
                ),
            },
        ),
        (
            "Registration information",
            {
                "fields": (
                    "tax_id",
                    "tax_registration_reason_code",
                    "state_registration_number",
                ),
            },
        ),
        (
            "Addresses",
            {
                "fields": (
                    "legal_address",
                    "actual_address",
                ),
            },
        ),
        (
            "Bank details",
            {
                "fields": (
                    "bank_name",
                    "bank_account",
                    "bank_code",
                    "correspondent_account",
                ),
            },
        ),
        (
            "Contacts",
            {
                "fields": (
                    "phone",
                    "email",
                ),
            },
        ),
    )

    def has_add_permission(
        self,
        request,
    ):
        return (
            CompanySettings.objects.count() < 1
        )

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "status",
        "order",
        "payment",
        "buyer_name",
        "amount",
        "currency_snapshot",
        "created_at",
    )

    list_filter = (
        "status",
        "currency_snapshot",
        "created_at",
    )

    search_fields = (
        "invoice_number",
        "buyer_name",
        "buyer_email",
        "buyer_company_name",
        "seller_company_name",
        "order__id",
        "payment__id",
    )

    readonly_fields = (
        "order",
        "payment",
        "invoice_number",
        "status",

        "seller_company_name",
        "seller_short_company_name",
        "seller_tax_id",
        "seller_tax_registration_reason_code",
        "seller_state_registration_number",
        "seller_legal_address",
        "seller_actual_address",
        "seller_bank_name",
        "seller_bank_account",
        "seller_bank_code",
        "seller_correspondent_account",
        "seller_phone",
        "seller_email",

        "buyer_name",
        "buyer_email",
        "buyer_phone",
        "buyer_address",
        "buyer_is_legal_entity",
        "buyer_company_name",
        "buyer_tax_id",
        "buyer_legal_address",
        "buyer_bank_name",
        "buyer_bank_account",

        "amount",
        "currency_snapshot",

        "cancel_comment",
        "cancelled_at",
        "cancelled_by",

        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False