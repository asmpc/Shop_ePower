from shop_epower.finance.models import AccountTransaction


def get_account_transactions(*, account):
    return AccountTransaction.objects.filter(account=account).order_by(
        "-created_at", "-pk"
    )


def get_financial_transactions_for_staff(*, operation_key=None):
    transactions = AccountTransaction.objects.select_related(
        "account", "account__user"
    ).order_by("-created_at", "-pk")

    operation_key = (operation_key or "").strip()
    if not operation_key:
        return transactions.none()

    return transactions.filter(operation_key__icontains=operation_key)
