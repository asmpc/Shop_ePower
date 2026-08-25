from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from shop_epower.accounts.models import Role
from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.core.currency import get_base_currency

from shop_epower.orders.tests.helpers import (
    create_test_order,
)
from shop_epower.payments.models import (
    Invoice,
    PaymentMethod,
    InvoiceStatus,
)
from shop_epower.payments.services import cancel_invoice
from shop_epower.payments.tests.helpers import (
    create_test_payment,
)


class TestsManagerInvoiceCancelAPI(TestCase):

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

        self.invoice = Invoice.objects.create(
            order=self.order,
            payment=self.payment,
            invoice_number="INV-2026-000001",

            seller_company_name="Shop ePower LLC",
            seller_short_company_name="Shop ePower",
            seller_tax_id="123456789",
            seller_tax_registration_reason_code="290101001",
            seller_state_registration_number="1152901008622",
            seller_legal_address="Seller legal address",
            seller_actual_address="Seller actual address",
            seller_bank_name="Seller Bank",
            seller_bank_account="BY00 TEST 0000 0000 0000 0000 0000",
            seller_bank_code="TESTBY22",
            seller_correspondent_account="30101810100000000601",
            seller_phone="+375291112233",
            seller_email="seller@test.com",

            buyer_name="Test Client",
            buyer_email="client@test.com",
            buyer_phone="+375291112233",
            buyer_address="Buyer address",
            buyer_is_legal_entity=False,

            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

    # Проверяем, что администратор
    # может отменить счёт.
    def test_admin_can_cancel_invoice(self):
        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-invoice-cancel",
            kwargs={
                "invoice_id": self.invoice.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "comment": "Invoice cancelled by administrator.",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.status,
            InvoiceStatus.CANCELLED,
        )

        self.assertEqual(
            self.invoice.cancel_comment,
            "Invoice cancelled by administrator.",
        )

        self.assertEqual(
            self.invoice.cancelled_by,
            self.admin,
        )

        self.assertIsNotNone(
            self.invoice.cancelled_at,
        )

    # Проверяем, что менеджер
    # не может отменить счёт.
    def test_manager_cannot_cancel_invoice(self):
        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-cancel",
            kwargs={
                "invoice_id": self.invoice.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "comment": "Cancel invoice",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # Проверяем, что клиент
    # не может отменить счёт.
    def test_client_cannot_cancel_invoice(self):
        self.client.force_authenticate(
            user=self.client_user,
        )

        url = reverse(
            "api-payments:manager-invoice-cancel",
            kwargs={
                "invoice_id": self.invoice.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "comment": "Cancel invoice",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # Проверяем, что неавторизованный пользователь
    # не может отменить счёт.
    def test_anonymous_cannot_cancel_invoice(self):
        url = reverse(
            "api-payments:manager-invoice-cancel",
            kwargs={
                "invoice_id": self.invoice.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "comment": "Cancel invoice",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Проверяем, что при попытке отменить
    # несуществующий счёт возвращается 404.
    def test_invoice_not_found(self):
        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-invoice-cancel",
            kwargs={
                "invoice_id": 999999,
            },
        )

        response = self.client.post(
            url,
            data={
                "comment": "Cancel invoice",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # Проверяем, что уже отменённый счёт
    # нельзя отменить повторно.
    def test_cannot_cancel_invoice_twice(self):
        cancel_invoice(
            invoice=self.invoice,
            cancelled_by=self.admin,
            comment="First cancellation.",
        )

        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-invoice-cancel",
            kwargs={
                "invoice_id": self.invoice.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "comment": "Second cancellation.",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Invoice is already cancelled.",
        )

    # Проверяем, что счёт нельзя отменить
    # без комментария.
    def test_cannot_cancel_invoice_without_comment(self):
        self.client.force_authenticate(
            user=self.admin,
        )

        url = reverse(
            "api-payments:manager-invoice-cancel",
            kwargs={
                "invoice_id": self.invoice.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "comment": "",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Cancellation comment is required.",
        )