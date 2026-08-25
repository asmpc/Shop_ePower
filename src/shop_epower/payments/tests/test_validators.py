from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import (
    DeliveryMethod,
    OrderStatus,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import PaymentMethod
from shop_epower.payments.services import (
    validate_client_can_pay_online,
    validate_payment_method_for_delivery,
)
from shop_epower.accounts.tests.helpers import create_test_user



class TestsPaymentValidators(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

    def create_order_with_status(
            self,
            *,
            status=OrderStatus.NEW,
    ):
        return create_test_order(
            user=self.user,
            status=status,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="",
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

    # Проверяем связку доставки и оплаты:
    # при самовывозе клиент может выбрать оплату при получении.
    def test_on_receipt_payment_is_allowed_for_pickup(self):
        validate_payment_method_for_delivery(
            delivery_method=DeliveryMethod.PICKUP,
            payment_method=PaymentMethod.ON_RECEIPT,
        )

    # Проверяем связку доставки и оплаты:
    # при доставке нельзя выбрать оплату при получении.
    def test_on_receipt_payment_is_not_allowed_for_shipping(self):
        with self.assertRaises(ValidationError):
            validate_payment_method_for_delivery(
                delivery_method=DeliveryMethod.SHIPPING,
                payment_method=PaymentMethod.ON_RECEIPT,
            )

    # Проверяем связку доставки и оплаты:
    # при доставке клиент может выбрать оплату по счету.
    def test_invoice_payment_is_allowed_for_shipping(self):
        validate_payment_method_for_delivery(
            delivery_method=DeliveryMethod.SHIPPING,
            payment_method=PaymentMethod.INVOICE,
        )

    # Проверяем связку доставки и оплаты:
    # при доставке клиент может выбрать online payment.
    def test_online_payment_is_allowed_for_shipping(self):
        validate_payment_method_for_delivery(
            delivery_method=DeliveryMethod.SHIPPING,
            payment_method=PaymentMethod.ONLINE,
        )

    # Проверяем online payment:
    # клиент может запустить online payment для нового заказа.
    def test_client_can_pay_online_for_new_order(self):
        order = self.create_order_with_status(
            status=OrderStatus.NEW,
        )

        validate_client_can_pay_online(
            order=order,
        )

    # Проверяем online payment:
    # клиент может запустить online payment для заказа в обработке.
    def test_client_can_pay_online_for_processing_order(self):
        order = self.create_order_with_status(
            status=OrderStatus.PROCESSING,
        )

        validate_client_can_pay_online(
            order=order,
        )

    # Проверяем защиту online payment:
    # клиент не может запустить online payment
    # для отмененного заказа.
    def test_client_cannot_pay_online_for_cancelled_order(self):
        order = self.create_order_with_status(
            status=OrderStatus.CANCELLED,
        )

        with self.assertRaises(ValidationError):
            validate_client_can_pay_online(
                order=order,
            )

    # Проверяем защиту online payment:
    # клиент не может запустить online payment
    # для завершенного заказа.
    def test_client_cannot_pay_online_for_completed_order(self):
        order = self.create_order_with_status(
            status=OrderStatus.COMPLETED,
        )

        with self.assertRaises(ValidationError):
            validate_client_can_pay_online(
                order=order,
            )