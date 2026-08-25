from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from shop_epower.accounts.models import Role
from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)

from shop_epower.orders.tests.helpers import (
    create_test_order,
)
from shop_epower.payments.models import PaymentStatus
from shop_epower.payments.tests.helpers import (
    create_test_payment,
)



class TestManagerPaymentActionsAPI(APITestCase):

    def setUp(self):
        self.manager = create_test_manager()

        self.client_user = create_test_user()

        self.admin = create_test_user(
            email="admin@example.com",
            username="admin",
            role=Role.ADMIN,
        )

        self.order = create_test_order(
            user=self.client_user,
        )

        self.payment = create_test_payment(
            order=self.order,
            status=PaymentStatus.PENDING,
        )

        self.url = reverse(
            "api-payments:manager-payment-mark-paid",
            kwargs={
                "pk": self.payment.pk,
            },
        )

    # Проверяем, что менеджер может
    # отметить ожидающий платеж как оплаченный.
    def test_manager_can_mark_payment_paid(self):

        self.client.force_authenticate(
            user=self.manager,
        )

        response = self.client.post(
            self.url,
            data={
                "comment": "Payment confirmed",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PAID,
        )

    # Проверяем, что менеджер получает 404
    # при попытке изменить несуществующий платеж.
    def test_manager_gets_404_for_missing_payment(self):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-mark-paid",
            kwargs={
                "pk": 999999,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # Проверяем, что неавторизованный пользователь
    # не может изменить статус платежа.
    def test_unauthenticated_user_cannot_mark_payment_paid(self):
        response = self.client.post(
            self.url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Проверяем, что клиент
    # не может изменить статус платежа.
    def test_client_cannot_mark_payment_paid(self):
        self.client.force_authenticate(
            user=self.client_user,
        )

        response = self.client.post(
            self.url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # Проверяем, что менеджер может
    # отметить ожидающий платеж как неуспешный.
    def test_manager_can_mark_payment_failed(self):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-mark-failed",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.FAILED,
        )

    # Проверяем, что менеджер может
    # отметить ожидающий платеж как отмененный.
    def test_manager_can_mark_payment_cancelled(self):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-mark-cancelled",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.CANCELLED,
        )

    # Проверяем, что менеджер получает 404
    # при попытке отметить несуществующий платеж как неуспешный.
    def test_manager_gets_404_for_missing_payment_when_marking_failed(
            self,
    ):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-mark-failed",
            kwargs={
                "pk": 999999,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # Проверяем, что неавторизованный пользователь
    # не может отметить платеж как неуспешный.
    def test_anonymous_cannot_mark_payment_failed(
            self,
    ):
        url = reverse(
            "api-payments:manager-payment-mark-failed",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Проверяем, что клиент не может
    # отметить платеж как неуспешный.
    def test_client_cannot_mark_payment_failed(
            self,
    ):
        self.client.force_authenticate(
            user=self.client_user,
        )

        url = reverse(
            "api-payments:manager-payment-mark-failed",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # Проверяем, что менеджер получает 404
    # при попытке отметить несуществующий платеж как отмененный.
    def test_manager_gets_404_for_missing_payment_when_marking_cancelled(
            self,
    ):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-mark-cancelled",
            kwargs={
                "pk": 999999,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # Проверяем, что неавторизованный пользователь
    # не может отметить платеж как отмененный.
    def test_anonymous_cannot_mark_payment_cancelled(
            self,
    ):
        url = reverse(
            "api-payments:manager-payment-mark-cancelled",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Проверяем, что клиент не может
    # отметить платеж как отмененный.
    def test_client_cannot_mark_payment_cancelled(
            self,
    ):
        self.client.force_authenticate(
            user=self.client_user,
        )

        url = reverse(
            "api-payments:manager-payment-mark-cancelled",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # Проверяем, что администратор может
    # вернуть завершенный платеж в статус ожидания.
    def test_admin_can_reset_payment_to_pending(
            self,
    ):
        self.payment.status = PaymentStatus.PAID

        self.payment.save(
            update_fields=[
                "status",
            ]
        )

        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-payment-reset-to-pending",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "comment": "Payment status corrected by admin.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            self.payment.manager_comment,
            "Payment status corrected by admin.",
        )

    # Проверяем, что менеджер не может
    # вернуть платеж в статус ожидания.
    def test_manager_cannot_reset_payment_to_pending(
            self,
    ):
        self.payment.status = PaymentStatus.PAID

        self.payment.save(
            update_fields=[
                "status",
            ]
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-payment-reset-to-pending",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "comment": "Manager tries to reset payment.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PAID,
        )

    # Проверяем, что неавторизованный пользователь
    # не может вернуть платеж в статус ожидания.
    def test_anonymous_cannot_reset_payment_to_pending(
            self,
    ):
        self.payment.status = PaymentStatus.PAID

        self.payment.save(
            update_fields=[
                "status",
            ]
        )

        url = reverse(
            "api-payments:manager-payment-reset-to-pending",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "comment": "Anonymous tries to reset payment.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PAID,
        )

    # Проверяем, что клиент не может
    # вернуть платеж в статус ожидания.
    def test_client_cannot_reset_payment_to_pending(
            self,
    ):
        self.payment.status = PaymentStatus.PAID

        self.payment.save(
            update_fields=[
                "status",
            ]
        )

        self.client.force_authenticate(
            user=self.client_user,
        )

        url = reverse(
            "api-payments:manager-payment-reset-to-pending",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "comment": "Client tries to reset payment.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PAID,
        )

    # Проверяем, что администратор получает 404,
    # если платеж не существует.
    def test_admin_cannot_reset_missing_payment_to_pending(
            self,
    ):
        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-payment-reset-to-pending",
            kwargs={
                "pk": 999999,
            },
        )

        response = self.client.post(
            url,
            {
                "comment": "Payment does not exist.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # Проверяем, что платеж в статусе ожидания
    # нельзя повторно вернуть в статус ожидания.
    def test_admin_cannot_reset_pending_payment_to_pending(
            self,
    ):
        self.payment.status = PaymentStatus.PENDING

        self.payment.save(
            update_fields=[
                "status",
            ]
        )

        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-payment-reset-to-pending",
            kwargs={
                "pk": self.payment.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "comment": "Repeated reset.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PENDING,
        )

