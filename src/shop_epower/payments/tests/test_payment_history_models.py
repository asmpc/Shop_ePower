from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import Order
from shop_epower.payments.models import (
    Payment,
    PaymentHistory,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)


User = get_user_model()


class TestsPaymentHistoryModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.manager = User.objects.create_user(
            email="manager@test.com",
            username="manager",
            password="testpass123",
            role="manager",
        )

        self.order = Order.objects.create(
            user=self.user,
            customer_name="Test Client",
            customer_email="client@test.com",
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.payment = Payment.objects.create(
            order=self.order,
            method=PaymentMethod.INVOICE,
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.MANUAL,
            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

    # Проверяем создание записи истории оплаты:
    # должны сохраняться старый и новый статусы.
    def test_create_payment_history(self):
        history = PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.PAID,
        )

        self.assertEqual(
            history.payment,
            self.payment,
        )

        self.assertEqual(
            history.old_status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            history.new_status,
            PaymentStatus.PAID,
        )

    # Проверяем сохранение комментария:
    # история должна хранить пояснение изменения.
    def test_payment_history_stores_comment(self):
        history = PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.FAILED,
            comment="Bank declined payment.",
        )

        self.assertEqual(
            history.comment,
            "Bank declined payment.",
        )

    # Проверяем сохранение пользователя:
    # должно быть понятно, кто выполнил изменение.
    def test_payment_history_stores_changed_by(self):
        history = PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.CANCELLED,
            changed_by=self.manager,
        )

        self.assertEqual(
            history.changed_by,
            self.manager,
        )

    # Проверяем связь payment -> history:
    # запись должна быть доступна через related_name.
    def test_payment_history_related_name(self):
        history = PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.PAID,
        )

        self.assertEqual(
            self.payment.history.count(),
            1,
        )

        self.assertEqual(
            self.payment.history.first(),
            history,
        )

    # Проверяем строковое представление:
    # должно содержать информацию о смене статуса.
    def test_payment_history_str(self):
        history = PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.PAID,
        )

        self.assertIn(
            "PENDING",
            str(history).upper(),
        )

        self.assertIn(
            "PAID",
            str(history).upper(),
        )

