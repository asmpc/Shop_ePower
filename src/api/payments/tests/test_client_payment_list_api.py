from django.test import TestCase
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.payments.tests.helpers import (
    create_test_payment_for_user,
)


class TestsClientPaymentListAPI(TestCase):

    def setUp(self):

        self.client = APIClient()

        self.user = create_test_user(
            email='payment-client@test.com',
            username='payment-client',
        )

        self.other_user = create_test_user(
            email='other-payment-client@test.com',
            username='other-payment-client',
        )

    # Проверяем, что клиент видит только платежи
    # собственных заказов.
    def test_client_payment_list_returns_only_own_payments(self):

        own_payment = create_test_payment_for_user(
            user=self.user,
        )

        other_payment = create_test_payment_for_user(
            user=self.other_user,
        )

        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            '/api/payments/my/',
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        payment_ids = [
            payment['id']
            for payment in response.data
        ]

        self.assertIn(
            own_payment.id,
            payment_ids,
        )

        self.assertNotIn(
            other_payment.id,
            payment_ids,
        )