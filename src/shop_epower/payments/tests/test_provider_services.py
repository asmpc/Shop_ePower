from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.core.currency import get_base_currency
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
)
from shop_epower.payments.services import (
    create_mock_payment_url,
    create_payment_for_order,
)


class TestsPaymentProviderServices(TestCase):

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

    # Проверяем создание mock payment URL:
    # online payment должен получить ссылку на mock checkout.
    def test_create_mock_payment_url_for_online_payment(self):
        payment = create_payment_for_order(
            order=self.order,
            method=PaymentMethod.ONLINE,
        )

        payment_url = create_mock_payment_url(
            payment=payment,
        )

        self.assertIn(
            "/payments/mock/",
            payment_url,
        )

        self.assertIn(
            payment.transaction_id,
            payment_url,
        )

        self.assertEqual(
            payment.provider,
            PaymentProvider.MOCK,
        )