from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import (
    create_legal_customer_account,
    create_personal_customer_account,
)
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

    # Фильтр по ID счёта разделяет личные и юридические поступления
    # одного клиента, даже при одинаковых сумме и способе оплаты.
    def test_account_filter_separates_personal_and_legal_receipts(self):
        profile = create_test_legal_profile(user=self.user)
        legal_account = create_legal_customer_account(
            legal_profile=profile,
        )

        receipt_data = {
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "created_by": self.manager,
        }

        personal_payment = record_manual_account_payment(
            account=self.account,
            operation_key="account-filter:personal:receipt",
            **receipt_data,
        )
        legal_payment = record_manual_account_payment(
            account=legal_account,
            operation_key="account-filter:legal:receipt",
            **receipt_data,
        )

        for account, expected_payment in (
            (self.account, personal_payment),
            (legal_account, legal_payment),
        ):
            with self.subTest(account_id=account.pk):
                payments = get_payments_for_manager(
                    account_id=account.pk,
                )

                self.assertEqual(
                    list(payments),
                    [expected_payment],
                )