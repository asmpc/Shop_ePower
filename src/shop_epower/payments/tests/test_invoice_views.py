from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import (
    DeliveryMethod,
    OrderStatus,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import (
    create_invoice_for_payment,
)
from shop_epower.payments.tests.helpers import (
    create_test_company_settings,
    create_test_payment,
)


class TestsInvoiceViews(TestCase):

    def setUp(self):
        self.client_user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.manager = create_test_manager(
            email="manager@test.com",
            username="manager",
            password="testpass123",
        )

        self.admin = create_test_admin(
            email="admin@test.com",
            username="admin",
            password="testpass123",
        )

        self.order = create_test_order(
            user=self.client_user,
            status=OrderStatus.PROCESSING,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="+375291112233",
            delivery_method=DeliveryMethod.SHIPPING,
            delivery_provider="post",
            delivery_address="Minsk, Main street, 10",
            delivery_cost=Decimal("20.00"),
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.MANUAL,
            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.company_settings = create_test_company_settings(
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

    def get_manager_order_list_url(self):
        return reverse(
            "orders:manager_order_list",
        )

    def get_expected_order_detail_url(self):
        manager_order_list_url = self.get_manager_order_list_url()

        manager_order_detail_url = reverse(
            "orders:manager_order_detail",
            args=[self.order.id],
        )

        return (
            f"{manager_order_detail_url}?"
            f"{urlencode({'next': manager_order_list_url})}"
        )

    # Проверяем manager workflow:
    # менеджер может создать invoice для оплаты по счету.
    def test_manager_can_generate_invoice(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "payments:manager_generate_invoice",
                args=[self.payment.id],
            ),
            data={
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

        self.assertEqual(
            Invoice.objects.count(),
            1,
        )

        invoice = Invoice.objects.first()

        self.assertEqual(
            invoice.payment,
            self.payment,
        )

    # Проверяем admin workflow:
    # администратор тоже может создать invoice.
    def test_admin_can_generate_invoice(self):
        self.client.force_login(
            self.admin,
        )

        response = self.client.post(
            reverse(
                "payments:manager_generate_invoice",
                args=[self.payment.id],
            ),
            data={
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

        self.assertEqual(
            Invoice.objects.count(),
            1,
        )

    # Проверяем права доступа:
    # клиент не может пользоваться manager endpoint
    # для создания invoice.
    def test_client_cannot_generate_invoice_from_manager_endpoint(self):
        self.client.force_login(
            self.client_user,
        )

        response = self.client.post(
            reverse(
                "payments:manager_generate_invoice",
                args=[self.payment.id],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            Invoice.objects.count(),
            0,
        )

    # Проверяем защиту от дублей:
    # второй invoice для одного payment создать нельзя.
    def test_cannot_generate_duplicate_invoice(self):
        self.client.force_login(
            self.manager,
        )

        generate_url = reverse(
            "payments:manager_generate_invoice",
            args=[self.payment.id],
        )

        request_data = {
            "next": self.get_manager_order_list_url(),
        }

        self.client.post(
            generate_url,
            data=request_data,
        )

        response = self.client.post(
            generate_url,
            data=request_data,
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

        self.assertEqual(
            Invoice.objects.count(),
            1,
        )

    # Проверяем права доступа:
    # менеджер не может отменить invoice,
    # так как отмена доступна только администратору.
    def test_manager_cannot_cancel_invoice(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "payments:admin_cancel_invoice",
                args=[invoice.id],
            ),
            data={
                "cancel_comment": "Wrong invoice data",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.status,
            "issued",
        )

    # Проверяем workflow:
    # администратор может отменить invoice.
    def test_admin_can_cancel_invoice(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        self.client.force_login(
            self.admin,
        )

        order_url = reverse(
            "orders:manager_order_detail",
            args=[self.order.id],
        )

        payment_url = reverse(
            "payments:manager_payment_detail",
            args=[self.payment.id],
        )

        expected_url = (
            f"{payment_url}?"
            f"{urlencode({'next': order_url})}"
        )

        response = self.client.post(
            reverse(
                "payments:admin_cancel_invoice",
                args=[invoice.id],
            ),
            data={
                "cancel_comment": "Wrong invoice data",
                "next": order_url,
            },
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.status,
            "cancelled",
        )

        self.assertEqual(
            invoice.cancel_comment,
            "Wrong invoice data",
        )

        self.assertEqual(
            invoice.cancelled_by,
            self.admin,
        )

        self.assertIsNotNone(
            invoice.cancelled_at,
        )

        self.assertRedirects(
            response,
            expected_url,
        )

    # Проверяем защиту:
    # повторная отмена invoice через endpoint
    # должна корректно обработать ValidationError.
    def test_cannot_cancel_invoice_twice(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        self.client.force_login(
            self.admin,
        )

        order_url = reverse(
            "orders:manager_order_detail",
            args=[self.order.id],
        )

        payment_url = reverse(
            "payments:manager_payment_detail",
            args=[self.payment.id],
        )

        expected_url = (
            f"{payment_url}?"
            f"{urlencode({'next': order_url})}"
        )

        cancel_url = reverse(
            "payments:admin_cancel_invoice",
            args=[invoice.id],
        )

        self.client.post(
            cancel_url,
            data={
                "cancel_comment": "First cancellation",
                "next": order_url,
            },
        )

        response = self.client.post(
            cancel_url,
            data={
                "cancel_comment": "Wrong invoice data",
                "next": order_url,
            },
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.cancel_comment,
            "First cancellation",
        )

        self.assertRedirects(
            response,
            expected_url,
        )
