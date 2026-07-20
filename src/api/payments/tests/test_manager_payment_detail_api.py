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
    create_payment,
)


class TestsManagerPaymentDetailAPI(TestCase):

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

        self.payment = create_payment(
            order=self.order,
        )

        self.path = reverse(
            "api-payments:manager-payment-detail",
            kwargs={
                "pk": self.payment.pk,
            },
        )

    # Менеджер может получить детали платежа
    def test_manager_can_get_payment_detail(self):
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
            response.data["id"],
            self.payment.id,
        )

        self.assertEqual(
            response.data["order"],
            self.order.id,
        )

        self.assertEqual(
            response.data["status"],
            self.payment.status,
        )

        self.assertEqual(
            response.data["method"],
            self.payment.method,
        )

        self.assertEqual(
            response.data["provider"],
            self.payment.provider,
        )

        self.assertEqual(
            response.data["amount"],
            str(self.payment.amount),
        )

        self.assertEqual(
            response.data["currency_snapshot"],
            self.payment.currency_snapshot,
        )

    # Администратор может получить детали платежа
    def test_admin_can_get_payment_detail(self):
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
            response.data["id"],
            self.payment.id,
        )

    # Клиент не может получить детали платежа для управления
    def test_client_cannot_get_payment_detail(self):
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

    # Неавторизованный пользователь не может получить детали платежа
    def test_unauthorized_user_cannot_get_payment_detail(self):
        response = self.client.get(
            path=self.path,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Проверяем, что менеджер получает 404,
    # если запрашиваемый платеж не существует.
    def test_manager_get_nonexistent_payment_returns_404(self):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-detail",
            kwargs={"pk": 999999},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )