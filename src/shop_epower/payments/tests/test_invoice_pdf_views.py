from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import Order
from shop_epower.payments.models import (
    CompanySettings,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import (
    create_invoice_for_payment,
)


User = get_user_model()


class TestsInvoicePdfViews(TestCase):

    def setUp(self):
        self.client_user = User.objects.create_user(
            email="client@test.com",
            username="client",
            password="testpass123",
            role="client",
        )

        self.other_client = User.objects.create_user(
            email="other-client@test.com",
            username="other-client",
            password="testpass123",
            role="client",
        )

        self.manager = User.objects.create_user(
            email="manager@test.com",
            username="manager",
            password="testpass123",
            role="manager",
        )

        self.admin = User.objects.create_user(
            email="admin@test.com",
            username="admin",
            password="testpass123",
            role="admin",
        )

        self.order = Order.objects.create(
            user=self.client_user,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="+375291112233",
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.payment = Payment.objects.create(
            order=self.order,
            method=PaymentMethod.INVOICE,
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.MANUAL,
            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        CompanySettings.objects.create(
            company_name="Shop ePower LLC",
            short_company_name="Shop ePower",
            tax_id="123456789",
            tax_registration_reason_code="290101001",
            state_registration_number="1152901008622",
            legal_address="Seller legal address",
            actual_address="Seller actual address",
            bank_name="Seller Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
            bank_code="TESTBY22",
            correspondent_account="30101810100000000601",
            phone="+375291112233",
            email="seller@test.com",
        )

        self.invoice = create_invoice_for_payment(
            payment=self.payment,
        )

    # Проверяем клиентский PDF endpoint:
    # владелец заказа может скачать свой invoice.
    def test_client_can_download_own_invoice_pdf(self):
        self.client.force_login(
            self.client_user,
        )

        response = self.client.get(
            reverse(
                "payments:client_invoice_pdf",
                args=[self.invoice.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )

        self.assertTrue(
            response.content.startswith(
                b"%PDF",
            )
        )

        self.assertIn(
            self.invoice.invoice_number,
            response["Content-Disposition"],
        )

    # Проверяем защиту клиентского endpoint:
    # другой клиент не может скачать чужой invoice.
    def test_other_client_cannot_download_invoice_pdf(self):
        self.client.force_login(
            self.other_client,
        )

        response = self.client.get(
            reverse(
                "payments:client_invoice_pdf",
                args=[self.invoice.id],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    # Проверяем authentication:
    # неавторизованный пользователь должен быть
    # перенаправлен на страницу входа.
    def test_anonymous_user_cannot_download_invoice_pdf(self):
        invoice_pdf_url = reverse(
            "payments:client_invoice_pdf",
            args=[self.invoice.id],
        )

        response = self.client.get(
            invoice_pdf_url,
        )

        expected_login_url = (
            f"{reverse('accounts:login')}"
            f"?next={invoice_pdf_url}"
        )

        self.assertRedirects(
            response,
            expected_login_url,
        )

    # Проверяем manager endpoint:
    # менеджер может скачать invoice.
    def test_manager_can_download_invoice_pdf(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "payments:manager_invoice_pdf",
                args=[self.invoice.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )

        self.assertTrue(
            response.content.startswith(
                b"%PDF",
            )
        )

        self.assertIn(
            self.invoice.invoice_number,
            response["Content-Disposition"],
        )

    # Проверяем admin endpoint:
    # администратор может скачать invoice.
    def test_admin_can_download_invoice_pdf(self):
        self.client.force_login(
            self.admin,
        )

        response = self.client.get(
            reverse(
                "payments:manager_invoice_pdf",
                args=[self.invoice.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )

        self.assertTrue(
            response.content.startswith(
                b"%PDF",
            )
        )

        self.assertIn(
            self.invoice.invoice_number,
            response["Content-Disposition"],
        )

    # Проверяем права доступа manager endpoint:
    # обычный клиент не может пользоваться
    # служебным endpoint скачивания invoice.
    def test_client_cannot_use_manager_invoice_pdf_endpoint(self):
        self.client.force_login(
            self.client_user,
        )

        response = self.client.get(
            reverse(
                "payments:manager_invoice_pdf",
                args=[self.invoice.id],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )