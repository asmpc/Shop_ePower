from decimal import Decimal

from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.selectors import (
    get_payments_for_manager,
)
from shop_epower.accounts.tests.helpers import create_test_user



class TestsPaymentSelectors(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.order_pending = create_test_order(
            user=self.user,
            customer_name="Pending Client",
            customer_email="pending@test.com",
            customer_phone="",
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.order_paid = create_test_order(
            user=self.user,
            customer_name="Paid Client",
            customer_email="paid@test.com",
            customer_phone="",
            total_price=Decimal("200.00"),
            currency_snapshot=get_base_currency(),
        )

        self.pending_payment = Payment.objects.create(
            order=self.order_pending,
            method=PaymentMethod.INVOICE,
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.MANUAL,
            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.paid_payment = Payment.objects.create(
            order=self.order_paid,
            method=PaymentMethod.ONLINE,
            status=PaymentStatus.PAID,
            provider=PaymentProvider.MOCK,
            amount=Decimal("200.00"),
            currency_snapshot=get_base_currency(),
        )

    # Проверяем, что selector возвращает все оплаты
    # для manager/admin списка.
    def test_get_payments_for_manager_returns_all_payments(self):
        payments = get_payments_for_manager()

        self.assertEqual(
            list(payments),
            [
                self.paid_payment,
                self.pending_payment,
            ],
        )

    # Проверяем фильтр по статусу оплаты.
    def test_get_payments_for_manager_filters_by_status(self):
        payments = get_payments_for_manager(
            status=PaymentStatus.PENDING,
        )

        self.assertEqual(
            list(payments),
            [
                self.pending_payment,
            ],
        )

    # Проверяем фильтр по способу оплаты.
    def test_get_payments_for_manager_filters_by_method(self):
        payments = get_payments_for_manager(
            method=PaymentMethod.ONLINE,
        )

        self.assertEqual(
            list(payments),
            [
                self.paid_payment,
            ],
        )

    # Проверяем фильтр по payment provider.
    def test_get_payments_for_manager_filters_by_provider(self):
        payments = get_payments_for_manager(
            provider=PaymentProvider.MOCK,
        )

        self.assertEqual(
            list(payments),
            [
                self.paid_payment,
            ],
        )