from django.urls import reverse

from rest_framework import status
from rest_framework.test import (
    APIClient,
    APITestCase,
)

from shop_epower.accounts.models import Role
from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.orders.tests.helpers import (
    create_test_order,
)
from shop_epower.payments.models import (
    PaymentHistory,
    PaymentStatus,
)
from shop_epower.payments.tests.helpers import (
    create_test_payment,
)


class TestManagerPaymentHistoryAPI(
    APITestCase,
):

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

        self.client_user = create_test_user(
            email="client@test.com",
            username="client",
            role=Role.CLIENT,
        )

        self.order = create_test_order(
            user=self.client_user,
        )

        self.payment = create_test_payment(
            order=self.order,
        )

    # Проверяем, что менеджер
    # может получить историю платежа.
    def test_manager_can_get_payment_history(
            self,
    ):
        PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.PAID,
            comment="Payment confirmed.",
            changed_by=self.manager,
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-history",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.get(
            url,
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
            response.data[0]["new_status"],
            PaymentStatus.PAID,
        )

    # Проверяем, что администратор
    # может получить историю платежа.
    def test_admin_can_get_payment_history(
            self,
    ):
        PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.PAID,
            comment="Payment confirmed.",
            changed_by=self.admin,
        )

        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-payment-history",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

    # Проверяем, что клиент
    # не может получить историю платежа.
    def test_client_cannot_get_payment_history(
            self,
    ):
        self.client.force_authenticate(
            user=self.client_user,
        )

        url = reverse(
            "api-payments:manager-payment-history",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # Проверяем, что анонимный пользователь
    # не может получить историю платежа.
    def test_anonymous_cannot_get_payment_history(
            self,
    ):
        url = reverse(
            "api-payments:manager-payment-history",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Проверяем, что при запросе истории
    # несуществующего платежа возвращается 404.
    def test_payment_history_returns_not_found(
            self,
    ):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-history",
            kwargs={
                "pk": 999999,
            },
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # Проверяем, что история платежа
    # возвращается от новых записей к старым.
    def test_payment_history_is_ordered_by_created_at_desc(
            self,
    ):
        PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.PAID,
            comment="First",
            changed_by=self.manager,
        )

        PaymentHistory.objects.create(
            payment=self.payment,
            old_status=PaymentStatus.PAID,
            new_status=PaymentStatus.CANCELLED,
            comment="Second",
            changed_by=self.manager,
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-history",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            2,
        )

        self.assertEqual(
            response.data[0]["comment"],
            "Second",
        )

        self.assertEqual(
            response.data[1]["comment"],
            "First",
        )