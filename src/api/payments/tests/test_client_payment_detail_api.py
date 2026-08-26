from django.test import TestCase
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.payments.tests.helpers import (
    create_test_payment,
    create_test_payment_for_user,
)


class TestsClientPaymentDetailAPI(TestCase):

    def setUp(self):

        self.client = APIClient()

        self.user = create_test_user(
            email='payment-detail-client@test.com',
            username='payment-detail-client',
        )

        self.other_user = create_test_user(
            email='other-payment-detail-client@test.com',
            username='other-payment-detail-client',
        )

    # Проверяем, что клиент может получить
    # платёж собственного заказа.
    def test_client_can_get_own_payment(self):

        payment = create_test_payment_for_user(
            user=self.user,
        )

        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            f'/api/payments/my/{payment.id}/',
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.data['id'],
            payment.id,
        )

        self.assertEqual(
            response.data['order_id'],
            payment.order_id,
        )

    # Проверяем, что клиент не может получить
    # платёж чужого заказа.
    def test_client_cannot_get_other_user_payment(self):

        other_payment = create_test_payment_for_user(
            user=self.other_user,
        )

        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            f'/api/payments/my/{other_payment.id}/',
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    # Проверяем, что неавторизованный пользователь
    # не может получить платёж.
    def test_unauthorized_user_cannot_get_payment(self):

        payment = create_test_payment_for_user(
            user=self.user,
        )

        response = self.client.get(
            f'/api/payments/my/{payment.id}/',
        )

        self.assertEqual(
            response.status_code,
            401,
        )

