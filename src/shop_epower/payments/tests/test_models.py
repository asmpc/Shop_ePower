from decimal import Decimal

from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import Order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.tests.helpers import create_payment
from shop_epower.accounts.tests.helpers import create_test_user



class TestsPaymentModel(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.order = Order.objects.create(
            user=self.user,
            customer_name="Test Client",
            customer_email="client@test.com",
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

    # Проверяем создание payment:
    # платеж создаётся для конкретного заказа,
    # способ оплаты, сумма и валюта сохраняются корректно.
    def test_payment_can_be_created(self):
        payment = create_payment(
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
        payment = create_payment(
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
        payment = create_payment(
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
        payment = create_payment(
            order=self.order,
            method=PaymentMethod.ONLINE,
        )

        self.assertTrue(payment.transaction_id)

        self.assertEqual(
            len(payment.transaction_id),
            32,
        )

    # Проверяем связь заказа и платежа:
    # у заказа должен быть доступ к платежу
    # через related_name payment.
    def test_order_has_payment_relation(self):
        payment = create_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
        )

        self.assertEqual(
            self.order.payment,
            payment,
        )

    # Проверяем строковое отображение payment:
    # объект должен удобно отображаться в админке,
    # логах и debug-сценариях.
    def test_payment_string_representation(self):
        payment = create_payment(
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