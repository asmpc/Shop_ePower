from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.core.currency import get_base_currency
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.tests.helpers import create_test_payment


class TestsPaymentModel(TestCase):

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
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

    # Проверяем допустимые статусы платежа:
    # устаревший FAILED не должен присутствовать
    # в действующем перечислении PaymentStatus.
    def test_failed_is_not_available_payment_status(self):
        self.assertNotIn(
            "failed",
            PaymentStatus.values,
        )

    # Проверяем создание payment:
    # платеж создаётся для конкретного заказа,
    # способ оплаты, сумма и валюта сохраняются корректно.
    def test_payment_can_be_created(self):
        payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
        )

        self.assertEqual(payment.order, self.order)
        self.assertEqual(payment.method, PaymentMethod.INVOICE)
        self.assertEqual(payment.amount, Decimal("100.00"))
        self.assertEqual(
            payment.currency_snapshot,
            get_base_currency(),
        )

    # Проверяем значения по умолчанию:
    # новый платеж создаётся в статусе PENDING,
    # а провайдер по умолчанию MANUAL.
    def test_payment_has_default_status_and_provider(self):
        payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.ON_RECEIPT,
        )

        self.assertEqual(
            payment.status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            payment.provider,
            PaymentProvider.MANUAL,
        )

    # Проверяем валюту по умолчанию:
    # новый платеж должен использовать
    # базовую валюту проекта.
    def test_payment_uses_base_currency_by_default(self):
        payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
        )

        self.assertEqual(
            payment.currency_snapshot,
            get_base_currency(),
        )

    # Проверяем генерацию transaction_id:
    # при создании платежа идентификатор транзакции
    # должен создаваться автоматически.
    def test_payment_transaction_id_is_generated_automatically(self):
        payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.ONLINE,
        )

        self.assertTrue(payment.transaction_id)

        self.assertEqual(
            len(payment.transaction_id),
            32,
        )

    # Проверяем несколько платежей одного заказа:
    # отдельные частичные оплаты сохраняются независимо,
    # а обратная связь payments возвращает оба платежа.
    def test_order_can_have_multiple_payments(self):
        first_payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("40.00"),
        )
        second_payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("60.00"),
        )

        self.assertCountEqual(
            self.order.payments.all(),
            [first_payment, second_payment],
        )

    # Проверяем строковое отображение payment:
    # объект должен удобно отображаться в админке,
    # логах и debug-сценариях.
    def test_payment_string_representation(self):
        payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
        )

        self.assertEqual(
            str(payment),
            (
                f"Payment #{payment.pk} "
                f"for Order #{self.order.pk} "
                f"({payment.status})"
            ),
        )