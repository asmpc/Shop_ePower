from decimal import Decimal

from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import Order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentStatus,
)
from shop_epower.payments.services import (
    create_payment_for_order,
)
from shop_epower.accounts.tests.helpers import create_test_user



class TestsPaymentViews(TestCase):

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

    # Проверяем открытие mock checkout page.
    def test_mock_checkout_page(self):
        payment = create_payment_for_order(
            order=self.order,
            method=PaymentMethod.ONLINE,
        )

        response = self.client.get(
            f"/payments/mock/{payment.transaction_id}/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context["payment"],
            payment,
        )

    # Проверяем успешную mock оплату.
    def test_mock_payment_success(self):
        payment = create_payment_for_order(
            order=self.order,
            method=PaymentMethod.ONLINE,
        )

        response = self.client.post(
            f"/payments/mock/{payment.transaction_id}/success/"
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            PaymentStatus.PAID,
        )

    # Проверяем неуспешную mock оплату.
    def test_mock_payment_fail(self):
        payment = create_payment_for_order(
            order=self.order,
            method=PaymentMethod.ONLINE,
        )

        response = self.client.post(
            f"/payments/mock/{payment.transaction_id}/fail/"
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            PaymentStatus.FAILED,
        )