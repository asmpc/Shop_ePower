from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.finance.models import (
    CustomerAccount,
    CustomerAccountStatus,
    CustomerAccountStatusHistory,
    CustomerAccountType,
)


class TestsCustomerAccountStatusHistoryModel(TestCase):
    def setUp(self):
        self.user = create_test_user(
            email="finance-status-client@test.com",
            username="finance-status-client",
            password="testpass123",
        )

        self.account = CustomerAccount.objects.create(
            user=self.user,
            account_type=CustomerAccountType.PERSONAL,
        )

    # Проверяем создание записи истории статуса:
    # запись хранит счёт, старый и новый статусы,
    # причину, инициатора и время изменения.
    def test_customer_account_status_history_can_be_created(self):
        history = CustomerAccountStatusHistory.objects.create(
            account=self.account,
            old_status=CustomerAccountStatus.ACTIVE,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Customer account was deactivated.",
            changed_by=self.user,
        )

        self.assertEqual(
            history.account,
            self.account,
        )
        self.assertEqual(
            history.old_status,
            CustomerAccountStatus.ACTIVE,
        )
        self.assertEqual(
            history.new_status,
            CustomerAccountStatus.INACTIVE,
        )
        self.assertEqual(
            history.reason,
            "Customer account was deactivated.",
        )
        self.assertEqual(
            history.changed_by,
            self.user,
        )
        self.assertIsNotNone(
            history.created_at,
        )

    # Проверяем, что для получения истории статусов счёта
    # в хронологическом порядке определён составной индекс.
    def test_status_history_has_account_created_at_index(self):
        index_fields = [
            tuple(index.fields) for index in CustomerAccountStatusHistory._meta.indexes
        ]

        self.assertIn(
            ("account", "created_at"),
            index_fields,
        )
