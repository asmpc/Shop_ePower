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
