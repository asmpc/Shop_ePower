from decimal import Decimal

from shop_epower.payments.models import (
    CompanySettings,
    Payment,
    PaymentMethod,
)


def create_test_payment(
    *,
    order,
    method=PaymentMethod.INVOICE,
    amount=Decimal("100.00"),
    **kwargs,
):
    return Payment.objects.create(
        order=order,
        method=method,
        amount=amount,
        **kwargs,
    )


def create_test_company_settings(
    **kwargs,
):
    defaults = {
        "company_name": "Test Company",
        "tax_id": "123456789",
        "legal_address": "Test legal address",
        "bank_name": "Test Bank",
        "bank_account": "BY00TEST0000000000000000000000",
    }

    defaults.update(kwargs)

    return CompanySettings.objects.create(
        **defaults,
    )