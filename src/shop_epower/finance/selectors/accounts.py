from django.db.models import Q

from shop_epower.finance.models import (
    CustomerAccount,
    CustomerAccountType,
)


def get_customer_accounts(
    *,
    user,
):
    return CustomerAccount.objects.filter(
        user=user,
    )


def get_personal_customer_account(
    *,
    user,
):
    return (
        get_customer_accounts(
            user=user,
        )
        .filter(
            account_type=CustomerAccountType.PERSONAL,
        )
        .first()
    )


def get_legal_customer_account(
    *,
    user,
):
    return (
        get_customer_accounts(
            user=user,
        )
        .filter(
            account_type=CustomerAccountType.LEGAL,
        )
        .first()
    )


def get_customer_accounts_for_staff(
    *,
    query=None,
    account_id=None,
    account_type=None,
    status=None,
):
    accounts = CustomerAccount.objects.select_related("user").order_by(
        "-created_at", "-pk"
    )

    if query is None and account_id is None and account_type is None and status is None:
        return accounts

    query = (query or "").strip()
    account_id = (account_id or "").strip()
    account_type = (account_type or "").strip()
    status = (status or "").strip()

    if not query and not account_id and not account_type and not status:
        return accounts.none()

    if query:
        accounts = accounts.filter(
            Q(user__email__icontains=query)
            | Q(user__phone__icontains=query)
            | Q(legal_tax_id_snapshot__icontains=query)
        )

    if account_id:
        try:
            account_number = int(account_id)
        except ValueError:
            return accounts.none()

        if not 1 <= account_number <= 2**63 - 1:
            return accounts.none()

        accounts = accounts.filter(pk=account_number)

    if account_type:
        accounts = accounts.filter(account_type=account_type)

    if status:
        accounts = accounts.filter(status=status)

    return accounts
