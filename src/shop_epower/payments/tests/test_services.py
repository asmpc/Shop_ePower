from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import Order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)

from shop_epower.payments.services import (
    create_payment_for_order,
    mark_payment_paid,
    mark_payment_failed,
    mark_payment_cancelled,
)

from shop_epower.payments.tests.helpers import (
    create_payment,
)


User = get_user_model()


class TestsPaymentServices(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.order = Order.objects.create(
            user=self.user,
            customer_name="Test Client",
            customer_email="client@test.com",
            total_price=Decimal("150.00"),
            currency_snapshot=get_base_currency(),
        )

    # Проверяем создание payment для заказа:
    # сумма и валюта платежа должны браться из заказа,
    # а статус по умолчанию должен быть PENDING.
    def test_create_payment_for_order(self):
        payment = create_payment_for_order(
            order=self.order,
            method=PaymentMethod.INVOICE,
        )

        self.assertEqual(payment.order, self.order)
        self.assertEqual(payment.amount, self.order.total_price)
        self.assertEqual(
            payment.currency_snapshot,
            self.order.currency_snapshot,
        )
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    # Проверяем выбор provider для оплаты по счету:
    # invoice-платеж должен обрабатываться вручную менеджером.
    def test_create_invoice_payment_uses_manual_provider(self):
        payment = create_payment_for_order(
            order=self.order,
            method=PaymentMethod.INVOICE,
        )

        self.assertEqual(
            payment.provider,
            PaymentProvider.MANUAL,
        )

    # Проверяем выбор provider для оплаты при получении:
    # on_receipt-платеж также должен обрабатываться вручную.
    def test_create_on_receipt_payment_uses_manual_provider(self):
        payment = create_payment_for_order(
            order=self.order,
            method=PaymentMethod.ON_RECEIPT,
        )

        self.assertEqual(
            payment.provider,
            PaymentProvider.MANUAL,
        )

    # Проверяем выбор provider для online payment:
    # онлайн-оплата пока должна использовать mock provider.
    def test_create_online_payment_uses_mock_provider(self):
        payment = create_payment_for_order(
            order=self.order,
            method=PaymentMethod.ONLINE,
        )

        self.assertEqual(
            payment.provider,
            PaymentProvider.MOCK,
        )

    # Проверяем успешную оплату:
    # pending payment может быть переведен в PAID.
    def test_mark_payment_paid(self):
        payment = create_payment(
            order=self.order,
        )

        mark_payment_paid(
            payment=payment,
            manager_comment="Invoice paid.",
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            PaymentStatus.PAID,
        )

        self.assertEqual(
            payment.manager_comment,
            "Invoice paid.",
        )

    # Проверяем неуспешную оплату:
    # pending payment может быть переведен в FAILED.
    def test_mark_payment_failed(self):
        payment = create_payment(
            order=self.order,
        )

        mark_payment_failed(
            payment=payment,
            manager_comment="Bank declined payment.",
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            PaymentStatus.FAILED,
        )

        self.assertEqual(
            payment.manager_comment,
            "Bank declined payment.",
        )

    # Проверяем отмену оплаты:
    # pending payment может быть переведен в CANCELLED.
    def test_mark_payment_cancelled(self):
        payment = create_payment(
            order=self.order,
        )

        mark_payment_cancelled(
            payment=payment,
            manager_comment="Payment cancelled by client.",
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            PaymentStatus.CANCELLED,
        )

        self.assertEqual(
            payment.manager_comment,
            "Payment cancelled by client.",
        )

    # Проверяем защиту payment workflow:
    # оплаченный платеж нельзя повторно перевести
    # в другой статус.
    def test_cannot_update_non_pending_payment(self):
        payment = create_payment(
            order=self.order,
        )

        mark_payment_paid(
            payment=payment,
        )

        with self.assertRaises(ValidationError):
            mark_payment_failed(
                payment=payment,
            )

