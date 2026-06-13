from django.contrib import admin
from django.test import TestCase

from shop_epower.payments.admin import PaymentAdmin
from shop_epower.payments.models import Payment


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