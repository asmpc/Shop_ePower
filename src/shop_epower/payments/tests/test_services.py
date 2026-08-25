from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.tests.helpers import create_test_order

from shop_epower.payments.services import (
    create_payment_for_order,
    mark_payment_paid,
    mark_payment_failed,
    mark_payment_cancelled,
    reset_payment_to_pending,
)

from shop_epower.payments.tests.helpers import (
    create_test_payment,
)

from shop_epower.payments.models import (
    PaymentHistory,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.accounts.tests.helpers import create_test_user



class TestsPaymentServices(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.order = create_test_order(
            user=self.user,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="",
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
        payment = create_test_payment(
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
        payment = create_test_payment(
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
        payment = create_test_payment(
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
        payment = create_test_payment(
            order=self.order,
        )

        mark_payment_paid(
            payment=payment,
        )

        with self.assertRaises(ValidationError):
            mark_payment_failed(
                payment=payment,
            )

    # Проверяем исправление ошибки оплаты:
    # оплаченный платеж можно вернуть в PENDING через service layer.
    def test_reset_paid_payment_to_pending(self):
        payment = create_test_payment(
            order=self.order,
        )

        mark_payment_paid(
            payment=payment,
        )

        reset_payment_to_pending(
            payment=payment,
            comment="Payment was marked as paid by mistake.",
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            payment.manager_comment,
            "Payment was marked as paid by mistake.",
        )

    # Проверяем исправление неуспешной оплаты:
    # failed payment можно вернуть в PENDING.
    def test_reset_failed_payment_to_pending(self):
        payment = create_test_payment(
            order=self.order,
        )

        mark_payment_failed(
            payment=payment,
        )

        reset_payment_to_pending(
            payment=payment,
            comment="Retry payment.",
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            PaymentStatus.PENDING,
        )

    # Проверяем исправление отмененной оплаты:
    # cancelled payment можно вернуть в PENDING.
    def test_reset_cancelled_payment_to_pending(self):
        payment = create_test_payment(
            order=self.order,
        )

        mark_payment_cancelled(
            payment=payment,
        )

        reset_payment_to_pending(
            payment=payment,
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            PaymentStatus.PENDING,
        )

    # Проверяем защиту payment workflow:
    # payment в статусе PENDING нельзя reset-ить в PENDING повторно.
    def test_cannot_reset_pending_payment_to_pending(self):
        payment = create_test_payment(
            order=self.order,
        )

        with self.assertRaises(ValidationError):
            reset_payment_to_pending(
                payment=payment,
            )

    # Проверяем payment history:
    # при успешной оплате должна создаваться запись истории.
    def test_mark_payment_paid_creates_payment_history(self):
        payment = create_test_payment(
            order=self.order,
        )

        mark_payment_paid(
            payment=payment,
            manager_comment="Invoice paid.",
            changed_by=self.user,
        )

        history = PaymentHistory.objects.get(
            payment=payment,
        )

        self.assertEqual(
            history.old_status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            history.new_status,
            PaymentStatus.PAID,
        )

        self.assertEqual(
            history.comment,
            "Invoice paid.",
        )

        self.assertEqual(
            history.changed_by,
            self.user,
        )

    # Проверяем payment history:
    # при неуспешной оплате должна создаваться запись истории.
    def test_mark_payment_failed_creates_payment_history(self):
        payment = create_test_payment(
            order=self.order,
        )

        mark_payment_failed(
            payment=payment,
            manager_comment="Bank declined payment.",
            changed_by=self.user,
        )

        history = PaymentHistory.objects.get(
            payment=payment,
        )

        self.assertEqual(
            history.old_status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            history.new_status,
            PaymentStatus.FAILED,
        )

        self.assertEqual(
            history.comment,
            "Bank declined payment.",
        )

        self.assertEqual(
            history.changed_by,
            self.user,
        )

    # Проверяем payment history:
    # при отмене оплаты должна создаваться запись истории.
    def test_mark_payment_cancelled_creates_payment_history(self):
        payment = create_test_payment(
            order=self.order,
        )

        mark_payment_cancelled(
            payment=payment,
            manager_comment="Client cancelled payment.",
            changed_by=self.user,
        )

        history = PaymentHistory.objects.get(
            payment=payment,
        )

        self.assertEqual(
            history.old_status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            history.new_status,
            PaymentStatus.CANCELLED,
        )

        self.assertEqual(
            history.comment,
            "Client cancelled payment.",
        )

        self.assertEqual(
            history.changed_by,
            self.user,
        )

    # Проверяем payment history:
    # при admin reset должна сохраняться история возврата в PENDING.
    def test_reset_payment_to_pending_creates_payment_history(self):
        payment = create_test_payment(
            order=self.order,
        )

        mark_payment_paid(
            payment=payment,
            changed_by=self.user,
        )

        PaymentHistory.objects.all().delete()

        reset_payment_to_pending(
            payment=payment,
            comment="Wrong order was marked as paid.",
            changed_by=self.user,
        )

        history = PaymentHistory.objects.get(
            payment=payment,
        )

        self.assertEqual(
            history.old_status,
            PaymentStatus.PAID,
        )

        self.assertEqual(
            history.new_status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            history.comment,
            "Wrong order was marked as paid.",
        )

        self.assertEqual(
            history.changed_by,
            self.user,
        )

