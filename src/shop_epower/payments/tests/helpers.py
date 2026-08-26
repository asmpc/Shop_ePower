from decimal import Decimal

from shop_epower.core.currency import get_base_currency
from shop_epower.payments.models import (
    CompanySettings,
    Invoice,
    Payment,
    PaymentHistory,
    PaymentMethod,
    PaymentStatus,
)
from shop_epower.orders.tests.helpers import create_test_order



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

def create_test_invoice(
    *,
    order,
    payment,
    invoice_number="INV-2026-000001",
    amount=Decimal("100.00"),
    **kwargs,
):
    defaults = {
        "seller_company_name": "Shop ePower LLC",
        "seller_short_company_name": "Shop ePower",
        "seller_tax_id": "123456789",
        "seller_tax_registration_reason_code": "290101001",
        "seller_state_registration_number": "1152901008622",
        "seller_legal_address": "Seller legal address",
        "seller_actual_address": "Seller actual address",
        "seller_bank_name": "Seller Bank",
        "seller_bank_account": "BY00 TEST 0000 0000 0000 0000 0000",
        "seller_bank_code": "TESTBY22",
        "seller_correspondent_account": "30101810100000000601",
        "seller_phone": "+375291112233",
        "seller_email": "seller@test.com",
        "buyer_name": "Test Client",
        "buyer_email": "client@test.com",
        "buyer_phone": "+375291112233",
        "buyer_address": "Buyer address",
        "buyer_is_legal_entity": False,
        "currency_snapshot": get_base_currency(),
    }

    defaults.update(kwargs)

    return Invoice.objects.create(
        order=order,
        payment=payment,
        invoice_number=invoice_number,
        amount=amount,
        **defaults,
    )

def create_test_payment_history(
    *,
    payment,
    old_status=PaymentStatus.PENDING,
    new_status=PaymentStatus.PAID,
    comment="Payment status changed.",
    changed_by=None,
    **kwargs,
):
    return PaymentHistory.objects.create(
        payment=payment,
        old_status=old_status,
        new_status=new_status,
        comment=comment,
        changed_by=changed_by,
        **kwargs,
    )

def create_test_payment_for_user(
    *,
    user,
    amount=Decimal("100.00"),
    **kwargs,
):
    order = create_test_order(
        user=user,
        total_price=amount,
    )

    return create_test_payment(
        order=order,
        amount=amount,
        **kwargs,
    )