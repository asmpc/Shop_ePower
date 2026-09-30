from django.contrib import admin

from shop_epower.finance.models import (
    AccountTransaction,
    CustomerAccount,
    CustomerAccountStatusHistory,
)


class ReadOnlyFinanceAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerAccount)
class CustomerAccountAdmin(ReadOnlyFinanceAdmin):
    readonly_fields = (
        "available_balance",
        "debt_balance",
        "status",
    )

    list_display = (
        "id",
        "user",
        "account_type",
        "status",
        "available_balance",
        "debt_balance",
        "currency",
    )
    search_fields = ("user__email", "legal_tax_id_snapshot")
    list_filter = ("account_type", "status")


@admin.register(AccountTransaction)
class AccountTransactionAdmin(ReadOnlyFinanceAdmin):
    list_display = (
        "id",
        "account",
        "operation_type",
        "available_delta",
        "debt_delta",
        "actor_type",
        "operation_key",
        "created_at",
    )
    search_fields = ("operation_key", "account__user__email")
    list_filter = ("operation_type", "actor_type")


@admin.register(CustomerAccountStatusHistory)
class CustomerAccountStatusHistoryAdmin(ReadOnlyFinanceAdmin):
    list_display = (
        "id",
        "account",
        "old_status",
        "new_status",
        "changed_by",
        "created_at",
    )
    search_fields = ("account__user__email", "changed_by__email", "reason")
    list_filter = ("old_status", "new_status")
