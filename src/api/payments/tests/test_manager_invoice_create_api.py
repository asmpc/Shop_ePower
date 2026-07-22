from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from rest_framework import status, response
from rest_framework.test import APIClient

from shop_epower.accounts.models import Role
from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.orders.models import (
    DeliveryMethod,
    OrderStatus,
)
from shop_epower.orders.services import (
    create_order_from_cart,
)
from shop_epower.orders.tests.helpers import (
    create_test_cart_with_item,
    create_test_product,
    create_test_supplier,
    create_test_supplier_product,
)
from shop_epower.payments.models import (
    Invoice,
    PaymentMethod,
)
from shop_epower.payments.tests.helpers import (
    create_company_settings,
    create_payment,
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

        create_company_settings()

    def create_invoice_payment(self):

        product = create_test_product(
            name="Invoice Product",
            brand_name="Invoice Brand",
            category_name="Invoice Category",
            manufacturer_article="INV-API-001",
            base_price=Decimal("100.00"),
        )

        supplier = create_test_supplier(
            name="Invoice Supplier",
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-INV-API-001",
            stock_quantity=10,
        )

        cart = create_test_cart_with_item(
            user=self.user,
            product=product,
            quantity=1,
            price_snapshot=Decimal("100.00"),
        )

        order = create_order_from_cart(
            user=self.user,
            cart=cart,
        )

        order.status = OrderStatus.PROCESSING
        order.delivery_method = DeliveryMethod.PICKUP

        order.save(
            update_fields=[
                "status",
                "delivery_method",
                "updated_at",
            ],
        )

        return create_payment(
            order=order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("100.00"),
        )

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
                "payment_id": payment.pk,
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
                payment=payment,
            ).exists(),
        )

        invoice = Invoice.objects.get(
            payment=payment,
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
                "payment_id": payment.pk,
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
                payment=payment,
            ).exists(),
        )

    # Проверяем, что неавторизованный пользователь
    # не может сформировать счёт.
    def test_anonymous_cannot_create_invoice(self):
        payment = self.create_invoice_payment()

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "payment_id": payment.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertFalse(
            Invoice.objects.filter(
                payment=payment,
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
                "payment_id": payment.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            Invoice.objects.filter(
                payment=payment,
            ).exists(),
        )

    # Проверяем, что нельзя сформировать
    # второй счёт для одного платежа.
    def test_cannot_create_second_invoice_for_payment(self):
        payment = self.create_invoice_payment()

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "payment_id": payment.pk,
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
                payment=payment,
            ).count(),
            1,
        )

        self.assertEqual(
            second_response.data["detail"],
            "Invoice already exists for this payment.",
        )

    # Проверяем, что нельзя сформировать
    # счёт для другого способа оплаты.
    def test_cannot_create_invoice_for_non_invoice_payment(self):
        payment = self.create_invoice_payment()

        payment.method = PaymentMethod.ON_RECEIPT
        payment.save(
            update_fields=[
                "method",
            ],
        )

        self.client.force_authenticate(
            user=self.manager,
        )

        url = reverse(
            "api-payments:manager-invoice-create",
            kwargs={
                "payment_id": payment.pk,
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
                payment=payment,
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
                "payment_id": payment.pk,
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
                payment=payment,
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
                "payment_id": payment.pk,
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
                payment=payment,
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
                "payment_id": payment.pk,
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
                payment=payment,
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
                "payment_id": payment.pk,
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
                payment=payment,
            ).exists(),
        )