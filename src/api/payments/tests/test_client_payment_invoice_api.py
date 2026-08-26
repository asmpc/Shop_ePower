from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import (
    create_test_order,
)
from shop_epower.payments.services import (
    create_invoice_for_payment,
)
from shop_epower.payments.tests.helpers import (
    create_test_company_settings,
    create_test_payment,
)


class TestsClientPaymentInvoiceAPI(TestCase):

    def setUp(self):

        self.client = APIClient()

        self.user = create_test_user(
            email="client@test.com",
            username="client",
        )

        self.other_user = create_test_user(
            email="other@test.com",
            username="other",
        )

        self.order = create_test_order(
            user=self.user,
            status=OrderStatus.PROCESSING,
        )

        self.payment = create_test_payment(
            order=self.order,
        )

        create_test_company_settings()

    # Проверяем, что клиент может получить
    # Invoice собственного платежа.
    def test_client_can_get_own_payment_invoice(self):

        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            f'/api/payments/my/{self.payment.id}/invoice/',
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.data['id'],
            invoice.id,
        )

        self.assertEqual(
            response.data['invoice_number'],
            invoice.invoice_number,
        )

        self.assertEqual(
            response.data['status'],
            invoice.status,
        )

        self.assertEqual(
            response.data['amount'],
            str(invoice.amount),
        )

        self.assertEqual(
            response.data['currency_snapshot'],
            invoice.currency_snapshot,
        )

    # Проверяем, что клиент не может получить
    # Invoice чужого платежа.
    def test_client_cannot_get_foreign_payment_invoice(self):

        create_invoice_for_payment(
            payment=self.payment,
        )

        another_user = create_test_user(
            email='another-payment-invoice@test.com',
            username='another-payment-invoice',
        )

        self.client.force_authenticate(
            user=another_user,
        )

        response = self.client.get(
            f'/api/payments/my/{self.payment.id}/invoice/',
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    # Проверяем, что неавторизованный клиент
    # не может получить Invoice платежа.
    def test_unauthorized_client_cannot_get_payment_invoice(self):

        create_invoice_for_payment(
            payment=self.payment,
        )

        response = self.client.get(
            f'/api/payments/my/{self.payment.id}/invoice/',
        )

        self.assertEqual(
            response.status_code,
            401,
        )

