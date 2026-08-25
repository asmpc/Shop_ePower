from decimal import Decimal

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
from shop_epower.payments.models import (
    PaymentMethod,
)
from shop_epower.payments.tests.helpers import (
    create_test_invoice,
    create_test_payment,
)



class TestsManagerInvoicePdfAPI(TestCase):

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
        )

        self.order = create_test_order(
            user=self.client_user,
        )

        self.payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("100.00"),
        )

        self.invoice = create_test_invoice(
            order=self.order,
            payment=self.payment,
        )

    # Проверяем, что менеджер
    # может скачать PDF счёта.
    def test_manager_can_download_invoice_pdf(self):

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-pdf",
            kwargs={
                "invoice_id": self.invoice.pk,
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
            response["Content-Type"],
            "application/pdf",
        )

    # Проверяем, что администратор
    # может скачать PDF счёта.
    def test_admin_can_download_invoice_pdf(self):
        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-invoice-pdf",
            kwargs={
                "invoice_id": self.invoice.pk,
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
            response["Content-Type"],
            "application/pdf",
        )

    # Проверяем, что клиент
    # не может скачать PDF счёта.
    def test_client_cannot_download_invoice_pdf(self):
        self.client.force_authenticate(
            user=self.client_user,
        )

        url = reverse(
            "api-payments:manager-invoice-pdf",
            kwargs={
                "invoice_id": self.invoice.pk,
            },
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # Проверяем, что неавторизованный пользователь
    # не может скачать PDF счёта.
    def test_anonymous_cannot_download_invoice_pdf(self):
        url = reverse(
            "api-payments:manager-invoice-pdf",
            kwargs={
                "invoice_id": self.invoice.pk,
            },
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Проверяем, что при запросе
    # несуществующего счёта возвращается 404.
    def test_invoice_pdf_not_found(self):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-pdf",
            kwargs={
                "invoice_id": 999999,
            },
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

