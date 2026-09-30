from decimal import Decimal

from django.contrib import admin
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls.base import reverse

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.finance.models import (
    AccountTransaction,
    AccountTransactionActorType,
    CustomerAccount,
    CustomerAccountStatus,
    CustomerAccountStatusHistory,
)
from shop_epower.finance.services import (
    change_customer_account_status,
    create_personal_customer_account,
    record_customer_deposit,
)


class TestsCustomerAccountAdmin(TestCase):
    # Остатки и статус счёта не редактируются напрямую в admin.
    def test_customer_account_balances_and_status_are_readonly(self):
        account_admin = admin.site._registry[CustomerAccount]

        self.assertIn("available_balance", account_admin.readonly_fields)
        self.assertIn("debt_balance", account_admin.readonly_fields)
        self.assertIn("status", account_admin.readonly_fields)

    # Финансовый счёт создаётся сервисом, а не вручную через admin.
    def test_customer_account_cannot_be_added_in_admin(self):
        superuser = create_test_user(
            is_staff=True,
            is_superuser=True,
        )
        request = RequestFactory().get("/admin/finance/customeraccount/add/")
        request.user = superuser

        account_admin = admin.site._registry[CustomerAccount]

        self.assertFalse(account_admin.has_add_permission(request))

    # Финансовый счёт нельзя удалить через Django admin.
    def test_customer_account_cannot_be_deleted_in_admin(self):
        superuser = create_test_user(
            is_staff=True,
            is_superuser=True,
        )
        request = RequestFactory().get("/admin/finance/customeraccount/")
        request.user = superuser

        account_admin = admin.site._registry[CustomerAccount]

        self.assertFalse(account_admin.has_delete_permission(request))

    # Счёт доступен для просмотра, но не для прямого редактирования.
    def test_customer_account_is_view_only_in_admin(self):
        superuser = create_test_user(
            is_staff=True,
            is_superuser=True,
        )
        request = RequestFactory().get("/admin/finance/customeraccount/")
        request.user = superuser

        account_admin = admin.site._registry[CustomerAccount]

        self.assertTrue(account_admin.has_view_permission(request))
        self.assertFalse(account_admin.has_change_permission(request))

    # Счета можно находить и проверять без открытия каждой записи.
    def test_customer_account_list_has_useful_fields_search_and_filters(self):
        account_admin = admin.site._registry[CustomerAccount]

        self.assertEqual(
            account_admin.list_display,
            (
                "id",
                "user",
                "account_type",
                "status",
                "available_balance",
                "debt_balance",
                "currency",
            ),
        )
        self.assertEqual(
            account_admin.search_fields,
            ("user__email", "legal_tax_id_snapshot"),
        )
        self.assertEqual(
            account_admin.list_filter,
            ("account_type", "status"),
        )


class TestsAccountTransactionAdmin(TestCase):
    # Финансовые операции доступны только для просмотра.
    def test_account_transactions_are_view_only_in_admin(self):
        superuser = create_test_user(
            is_staff=True,
            is_superuser=True,
        )
        request = RequestFactory().get("/admin/finance/accounttransaction/")
        request.user = superuser

        self.assertIn(AccountTransaction, admin.site._registry)
        transaction_admin = admin.site._registry[AccountTransaction]

        self.assertTrue(transaction_admin.has_view_permission(request))
        self.assertFalse(transaction_admin.has_add_permission(request))
        self.assertFalse(transaction_admin.has_change_permission(request))
        self.assertFalse(transaction_admin.has_delete_permission(request))

    # Журнал позволяет найти операцию и увидеть её основные данные.
    def test_account_transaction_list_has_search_and_filters(self):
        transaction_admin = admin.site._registry[AccountTransaction]

        self.assertEqual(
            transaction_admin.list_display,
            (
                "id",
                "account",
                "operation_type",
                "available_delta",
                "debt_delta",
                "actor_type",
                "operation_key",
                "created_at",
            ),
        )
        self.assertEqual(
            transaction_admin.search_fields,
            ("operation_key", "account__user__email"),
        )
        self.assertEqual(
            transaction_admin.list_filter,
            ("operation_type", "actor_type"),
        )


class TestsCustomerAccountStatusHistoryAdmin(TestCase):
    # История статусов доступна только для просмотра.
    def test_status_history_is_view_only_in_admin(self):
        superuser = create_test_user(
            is_staff=True,
            is_superuser=True,
        )
        request = RequestFactory().get("/admin/finance/customeraccountstatushistory/")
        request.user = superuser

        self.assertIn(CustomerAccountStatusHistory, admin.site._registry)
        history_admin = admin.site._registry[CustomerAccountStatusHistory]

        self.assertTrue(history_admin.has_view_permission(request))
        self.assertFalse(history_admin.has_add_permission(request))
        self.assertFalse(history_admin.has_change_permission(request))
        self.assertFalse(history_admin.has_delete_permission(request))

    # Историю можно найти по клиенту, инициатору или причине изменения.
    def test_status_history_list_has_search_and_filters(self):
        history_admin = admin.site._registry[CustomerAccountStatusHistory]

        self.assertEqual(
            history_admin.list_display,
            (
                "id",
                "account",
                "old_status",
                "new_status",
                "changed_by",
                "created_at",
            ),
        )
        self.assertEqual(
            history_admin.search_fields,
            ("account__user__email", "changed_by__email", "reason"),
        )
        self.assertEqual(
            history_admin.list_filter,
            ("old_status", "new_status"),
        )


class TestsFinanceAdminPages(TestCase):
    # Проверяем реальные HTTP-страницы списков и карточек.
    def test_superuser_can_open_finance_pages(self):
        superuser = create_test_user(is_staff=True, is_superuser=True)
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)

        operation = record_customer_deposit(
            account=account,
            amount=Decimal("10.00"),
            operation_key="admin-page-deposit-001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        change_customer_account_status(
            account=account,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Checking admin history page.",
        )
        history = account.status_history.get()

        self.client.force_login(superuser)

        for model_name, obj in (
            ("customeraccount", account),
            ("accounttransaction", operation),
            ("customeraccountstatushistory", history),
        ):
            with self.subTest(model=model_name):
                list_url = reverse(f"admin:finance_{model_name}_changelist")
                detail_url = reverse(
                    f"admin:finance_{model_name}_change",
                    args=[obj.pk],
                )

                self.assertEqual(self.client.get(list_url).status_code, 200)
                self.assertEqual(self.client.get(detail_url).status_code, 200)
                self.assertEqual(
                    self.client.get(list_url, {"q": customer.email}).status_code,
                    200,
                )
