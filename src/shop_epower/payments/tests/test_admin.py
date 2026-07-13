from django.contrib import admin
from django.test import TestCase
from django.test import RequestFactory

from shop_epower.payments.admin import (
    CompanySettingsAdmin,
    PaymentAdmin,
    PaymentHistoryAdmin,
)
from shop_epower.payments.models import (
    CompanySettings,
    Payment,
    PaymentHistory,
)


class TestsPaymentAdmin(TestCase):

    # Проверяем, что Payment зарегистрирован в Django admin.
    def test_payment_is_registered_in_admin(self):
        self.assertIsInstance(
            admin.site._registry[Payment],
            PaymentAdmin,
        )

    # Проверяем поля, которые отображаются в списке Payment.
    def test_payment_admin_list_display(self):
        payment_admin = admin.site._registry[Payment]

        self.assertEqual(
            payment_admin.list_display,
            (
                "id",
                "order",
                "method",
                "status",
                "provider",
                "amount",
                "currency_snapshot",
                "created_at",
            ),
        )

    # Проверяем фильтры Payment в Django admin.
    def test_payment_admin_list_filter(self):
        payment_admin = admin.site._registry[Payment]

        self.assertEqual(
            payment_admin.list_filter,
            (
                "method",
                "status",
                "provider",
                "created_at",
            ),
        )

    # Проверяем поиск Payment в Django admin.
    def test_payment_admin_search_fields(self):
        payment_admin = admin.site._registry[Payment]

        self.assertEqual(
            payment_admin.search_fields,
            (
                "transaction_id",
                "provider_payment_id",
                "order__id",
                "order__customer_email",
            ),
        )

    # Проверяем readonly поля Payment в Django admin.
    def test_payment_admin_readonly_fields(self):
        payment_admin = admin.site._registry[Payment]

        self.assertEqual(
            payment_admin.readonly_fields,
            (
                "order",
                "method",
                "provider",
                "amount",
                "currency_snapshot",
                "transaction_id",
                "created_at",
                "updated_at",
            ),
        )

    # Проверяем, что PaymentHistory зарегистрирован в Django admin.
    def test_payment_history_is_registered_in_admin(self):
        self.assertIsInstance(
            admin.site._registry[PaymentHistory],
            PaymentHistoryAdmin,
        )

    # Проверяем поля, которые отображаются в списке PaymentHistory.
    def test_payment_history_admin_list_display(self):
        payment_history_admin = admin.site._registry[PaymentHistory]

        self.assertEqual(
            payment_history_admin.list_display,
            (
                "id",
                "payment",
                "old_status",
                "new_status",
                "changed_by",
                "created_at",
            ),
        )

    # Проверяем readonly поля PaymentHistory:
    # audit trail нельзя редактировать вручную.
    def test_payment_history_admin_readonly_fields(self):
        payment_history_admin = admin.site._registry[PaymentHistory]

        self.assertEqual(
            payment_history_admin.readonly_fields,
            (
                "payment",
                "old_status",
                "new_status",
                "comment",
                "changed_by",
                "created_at",
            ),
        )

    # Проверяем, что CompanySettings зарегистрирован в Django admin.
    def test_company_settings_is_registered_in_admin(self):
        self.assertIsInstance(
            admin.site._registry[CompanySettings],
            CompanySettingsAdmin,
        )

    # Проверяем поля, которые отображаются в списке CompanySettings.
    def test_company_settings_admin_list_display(self):
        company_settings_admin = admin.site._registry[CompanySettings]

        self.assertEqual(
            company_settings_admin.list_display,
            (
                "company_name",
                "short_company_name",
                "tax_id",
                "bank_name",
                "phone",
                "updated_at",
            ),
        )

    # Проверяем мягкий singleton:
    # если реквизиты компании уже созданы,
    # вторую запись через admin добавить нельзя.
    def test_company_settings_admin_allows_only_one_record(self):
        request = RequestFactory().get("/admin/")

        company_settings_admin = admin.site._registry[CompanySettings]

        self.assertTrue(
            company_settings_admin.has_add_permission(
                request,
            )
        )

        CompanySettings.objects.create(
            company_name="Shop ePower LLC",
            tax_id="123456789",
            legal_address="Test legal address",
            bank_name="Test Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
        )

        self.assertFalse(
            company_settings_admin.has_add_permission(
                request,
            )
        )



