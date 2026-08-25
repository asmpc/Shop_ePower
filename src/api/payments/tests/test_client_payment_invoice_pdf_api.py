from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import (
    create_test_order,
)

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)

from shop_epower.payments.services import (
    create_invoice_for_payment,
)
from shop_epower.payments.tests.helpers import (
    create_test_company_settings,
    create_test_payment,
)


class TestsClientPaymentInvoicePDFAPI(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.user = create_test_user(
            email="client-pdf@test.com",
            username="client-pdf",
        )

        self.other_user = create_test_user(
            email="other-pdf@test.com",
            username="other-pdf",
        )

        create_test_company_settings()

        self.order = create_test_order(
            user=self.user,
            status=OrderStatus.PROCESSING,
        )

        self.payment = create_test_payment(
            order=self.order,
        )

        self.invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        self.url = reverse(
            "api-payments:client-payment-invoice-pdf",
            kwargs={
                "payment_id": self.payment.id,
            },
        )

    # Проверяем, что клиент может скачать
    # PDF собственного Invoice.
    def test_client_can_download_own_invoice_pdf(self):
        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )

        self.assertEqual(
            response["Content-Disposition"],
            (
                f'attachment; '
                f'filename="{self.invoice.invoice_number}.pdf"'
            ),
        )

        self.assertTrue(
            response.content.startswith(
                b"%PDF",
            )
        )

    # Проверяем, что клиент не может скачать
    # PDF Invoice чужого платежа.
    def test_client_cannot_download_foreign_invoice_pdf(self):
        self.client.force_authenticate(
            user=self.other_user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # Проверяем, что неавторизованный клиент
    # не может скачать PDF Invoice.
    def test_unauthorized_user_cannot_download_invoice_pdf(self):
        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Проверяем, что API возвращает 404,
    # если у платежа отсутствует Invoice.
    def test_client_receives_404_when_invoice_does_not_exist(self):
        order = create_test_order(
            user=self.user,
            status=OrderStatus.PROCESSING,
        )

        payment = create_test_payment(
            order=order,
        )

        url = reverse(
            "api-payments:client-payment-invoice-pdf",
            kwargs={
                "payment_id": payment.id,
            },
        )

        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )