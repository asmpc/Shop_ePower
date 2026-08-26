from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from shop_epower.accounts.models import Role
from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.orders.tests.helpers import (
    create_test_order,
)
from shop_epower.payments.tests.helpers import (
    create_test_payment,
)


class TestsManagerPaymentListAPI(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.manager = create_test_user(
            email="manager@test.com",
            username="manager",
            role=Role.MANAGER,
        )

        self.admin = create_test_user(
            email="admin@test.com",
            username="admin",
            role=Role.ADMIN,
        )

        self.customer = create_test_user(
            email="customer@test.com",
            username="customer",
            role=Role.CLIENT,
        )

        self.order = create_test_order(
            user=self.customer,
        )

        self.payment = create_test_payment(
            order=self.order,
        )

        self.path = reverse(
            "api-payments:manager-payment-list",
        )

    # Менеджер может получить список платежей
    def test_manager_can_get_payment_list(self):
        self.client.force_authenticate(
            user=self.manager,
        )

        response = self.client.get(
            path=self.path,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
            self.payment.id,
        )

    # Администратор может получить список платежей
    def test_admin_can_get_payment_list(self):
        self.client.force_authenticate(
            user=self.admin,
        )

        response = self.client.get(
            path=self.path,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

    # Клиент не может получить список платежей для управления
    def test_client_cannot_get_payment_list(self):
        self.client.force_authenticate(
            user=self.customer,
        )

        response = self.client.get(
            path=self.path,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # Неавторизованный пользователь не может получить список платежей
    def test_unauthorized_user_cannot_get_payment_list(self):
        response = self.client.get(
            path=self.path,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )