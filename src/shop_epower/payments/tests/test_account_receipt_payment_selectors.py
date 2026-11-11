from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.payments.models import PaymentMethod
from shop_epower.payments.selectors import get_payments_for_manager
from shop_epower.payments.services import record_manual_account_payment


class TestsAccountReceiptPaymentSelectors(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

    # Поиск сотрудника по email находит поступление без заказа.
    # Клиент определяется через пополнение и финансовый счёт.
    def test_staff_email_search_finds_receipt_without_order(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:staff-email-search",
            created_by=self.manager,
        )

        payments = get_payments_for_manager(
            customer_email=self.user.email,
        )

        self.assertEqual(list(payments), [payment])

    # Поиск по email исключает поступления другого клиента,
    # даже если сумма и способ оплаты совпадают.
    def test_staff_email_search_excludes_other_customer_receipts(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(user=other_user)

        receipt_data = {
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "created_by": self.manager,
        }

        payment = record_manual_account_payment(
            account=self.account,
            operation_key="account:receipt:email-search:own",
            **receipt_data,
        )

        record_manual_account_payment(
            account=other_account,
            operation_key="account:receipt:email-search:other",
            **receipt_data,
        )

        payments = get_payments_for_manager(
            customer_email=self.user.email,
        )

        self.assertEqual(list(payments), [payment])
