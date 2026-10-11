from shop_epower.finance.models import CustomerAccountStatusHistory


def get_account_status_history(*, account):
    return (
        CustomerAccountStatusHistory.objects.filter(account=account)
        .select_related("changed_by")
        .order_by("-created_at", "-pk")
    )
