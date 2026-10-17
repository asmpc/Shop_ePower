from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from shop_epower.accounts.models import Role
from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import (
    DeliveryMethod,
    OrderStatus,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    InvoiceStatus,
    PaymentMethod,
)
from shop_epower.payments.tests.helpers import (
    create_test_company_settings,
    create_test_payment_for_user,
)


class TestsManagerInvoiceCreateAPI(TestCase):

    def setUp(self):

        self.client = APIClient()

        self.manager = create_test_user(
            email="invoice-manager@test.com",
            username="invoice-manager",
            role=Role.MANAGER,
        )

        self.user = create_test_user(
            email="invoice-client@test.com",
            username="invoice-client",
        )

        create_test_company_settings()

    def create_invoice_payment(self):
        payment = create_test_payment_for_user(
            user=self.user,
            method=PaymentMethod.INVOICE,
            amount=Decimal("100.00"),
        )

        order = payment.order
        order.payment_method = PaymentMethod.INVOICE

        order.status = OrderStatus.PROCESSING
        order.delivery_method = DeliveryMethod.PICKUP

        order.save(
            update_fields=[
                "status",
                "delivery_method",
                "updated_at",
                "payment_method",
            ],
        )

        return payment

    def create_shipping_invoice_payment(self):
        payment = self.create_invoice_payment()

        order = payment.order

        order.delivery_method = DeliveryMethod.SHIPPING
        order.delivery_provider = "Test Delivery"
        order.delivery_address = "Test address"
        order.delivery_cost = Decimal("20.00")

        order.save(
            update_fields=[
                "delivery_method",
                "delivery_provider",
                "delivery_address",
                "delivery_cost",
                "updated_at",
            ],
        )

        return payment

    # Проверяем, что менеджер
    # может сформировать счёт для платежа.
    def test_manager_can_create_invoice(self):

        payment = self.create_invoice_payment()

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

        invoice = Invoice.objects.get(
            order=payment.order,
        )

        self.assertEqual(
            response.data["id"],
            invoice.pk,
        )

        self.assertEqual(
            response.data["invoice_number"],
            invoice.invoice_number,
        )

    # Проверяем, что клиент
    # не может сформировать счёт через manager API.
    def test_client_cannot_create_invoice(self):

        payment = self.create_invoice_payment()

        self.client.force_authenticate(
            user=self.user,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertFalse(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

    # Проверяем, что неавторизованный пользователь
    # не может сформировать счёт.
    def test_anonymous_cannot_create_invoice(self):
        payment = self.create_invoice_payment()

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertFalse(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

    # Проверяем, что администратор
    # может сформировать счёт.
    def test_admin_can_create_invoice(self):
        admin = create_test_user(
            email="admin@test.com",
            username="admin",
            role=Role.ADMIN,
        )

        payment = self.create_invoice_payment()

        self.client.force_authenticate(
            user=admin,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

    # Пока у заказа есть действующий Invoice,
    # повторная выписка должна возвращать ошибку.
    def test_cannot_create_second_issued_invoice_for_order(self):
        payment = self.create_invoice_payment()

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        first_response = self.client.post(
            url,
        )

        second_response = self.client.post(
            url,
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Invoice.objects.filter(
                order=payment.order,
            ).count(),
            1,
        )

        self.assertEqual(
            second_response.data["detail"],
            "An issued invoice already exists for this order.",
        )

    # Invoice нельзя выписать через этот сценарий,
    # если в заказе выбран другой способ оплаты.
    def test_cannot_create_invoice_for_non_invoice_order(self):
        payment = self.create_invoice_payment()

        order = payment.order
        order.payment_method = PaymentMethod.ON_RECEIPT
        order.save(
            update_fields=[
                "payment_method",
            ],
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Invoice can be created only for invoice payment method.",
        )

        self.assertFalse(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

    # Проверяем, что нельзя сформировать
    # счёт для заказа не в обработке.
    def test_cannot_create_invoice_for_order_not_processing(self):
        payment = self.create_invoice_payment()

        payment.order.status = OrderStatus.NEW
        payment.order.save(
            update_fields=[
                "status",
                "updated_at",
            ],
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Invoice can be generated only for an order in processing.",
        )

        self.assertFalse(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

    # Проверяем, что для доставки
    # должен быть выбран перевозчик.
    def test_cannot_create_invoice_without_delivery_provider(self):
        payment = self.create_shipping_invoice_payment()

        payment.order.delivery_provider = ""
        payment.order.save(
            update_fields=[
                "delivery_provider",
                "updated_at",
            ],
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Delivery provider must be selected before generating invoice.",
        )

        self.assertFalse(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

    # Проверяем, что для доставки
    # должен быть указан адрес.
    def test_cannot_create_invoice_without_delivery_address(self):
        payment = self.create_shipping_invoice_payment()

        payment.order.delivery_address = ""
        payment.order.save(
            update_fields=[
                "delivery_address",
                "updated_at",
            ],
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Delivery address must be specified before generating invoice.",
        )

        self.assertFalse(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

    # Проверяем, что для доставки
    # должна быть рассчитана стоимость.
    def test_cannot_create_invoice_without_delivery_cost(self):
        payment = self.create_shipping_invoice_payment()

        payment.order.delivery_cost = None
        payment.order.save(
            update_fields=[
                "delivery_cost",
                "updated_at",
            ],
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "order_id": payment.order_id,
            },
        )

        response = self.client.post(
            url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Delivery cost must be calculated before generating invoice.",
        )

        self.assertFalse(
            Invoice.objects.filter(
                order=payment.order,
            ).exists(),
        )

    # Менеджер выписывает Invoice по заказу без платежей через API.
    # Документ не создаёт поступление денег и не меняет балансы.
    def test_manager_can_create_invoice_without_payment(self):
        account = create_personal_customer_account(
            user=self.user,
        )
        order = create_test_order(
            user=self.user,
            customer_account=account,
            status=OrderStatus.PROCESSING,
            payment_method=PaymentMethod.INVOICE,
            customer_phone="+375291112233",
        )

        self.client.force_authenticate(
            user=self.manager,
        )
        response = self.client.post(
            reverse(
                "api-payments:manager-invoice-create",
                kwargs={"order_id": order.pk},
            ),
        )

        self.assertEqual(response.status_code, 201)

        invoice = Invoice.objects.get(order=order)
        self.assertEqual(response.data["id"], invoice.pk)
        self.assertEqual(
            response.data["invoice_number"],
            invoice.invoice_number,
        )
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, order.total_price)
        self.assertIsNone(invoice.payment_id)
        self.assertFalse(order.payments.exists())

        account.refresh_from_db()
        self.assertEqual(account.available_balance, Decimal("0.00"))
        self.assertEqual(account.debt_balance, Decimal("0.00"))
        self.assertFalse(account.transactions.exists())