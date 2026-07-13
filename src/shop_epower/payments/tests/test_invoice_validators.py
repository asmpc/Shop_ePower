from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import (
    DeliveryMethod,
    Order,
)
from shop_epower.payments.models import (
    Invoice,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.validators import (
    validate_client_can_create_invoice,
    validate_manager_can_create_invoice,
)


User = get_user_model()


class TestsInvoiceValidators(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.order = Order.objects.create(
            user=self.user,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="+375291112233",
            delivery_method=DeliveryMethod.PICKUP,
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

    # Проверяем правило для клиента:
    # клиент может создать invoice сам,
    # если выбран самовывоз и способ оплаты — по счету.
    def test_client_can_create_invoice_for_pickup_order(self):
        validate_client_can_create_invoice(
            payment=self.payment,
        )

    # Проверяем правило для клиента:
    # при доставке invoice должен быть доступен
    # только после согласования менеджером.
    def test_client_cannot_create_invoice_for_shipping_order(self):
        self.order.delivery_method = DeliveryMethod.SHIPPING
        self.order.save(
            update_fields=[
                "delivery_method",
            ]
        )

        with self.assertRaises(ValidationError):
            validate_client_can_create_invoice(
                payment=self.payment,
            )

    # Проверяем правило для менеджера:
    # менеджер может создать invoice даже при доставке,
    # потому что он отвечает за согласование условий.
    def test_manager_can_create_invoice_for_shipping_order(self):
        self.order.delivery_method = DeliveryMethod.SHIPPING
        self.order.save(
            update_fields=[
                "delivery_method",
            ]
        )

        validate_manager_can_create_invoice(
            payment=self.payment,
        )

    # Проверяем защиту:
    # invoice нельзя создать повторно для одного payment.
    def test_cannot_create_duplicate_invoice(self):
        Invoice.objects.create(
            order=self.order,
            payment=self.payment,
            invoice_number="INV-2026-000001",

            seller_company_name="Shop ePower LLC",
            seller_tax_id="123456789",
            seller_legal_address="Seller legal address",
            seller_bank_name="Seller Bank",
            seller_bank_account="BY00 TEST 0000 0000 0000 0000 0000",

            buyer_name="Test Client",
            buyer_email="client@test.com",
            buyer_phone="+375291112233",

            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        with self.assertRaises(ValidationError):
            validate_client_can_create_invoice(
                payment=self.payment,
            )

        with self.assertRaises(ValidationError):
            validate_manager_can_create_invoice(
                payment=self.payment,
            )

    # Проверяем защиту:
    # invoice нельзя создать для оплаты при получении.
    def test_cannot_create_invoice_for_on_receipt_payment(self):
        self.payment.method = PaymentMethod.ON_RECEIPT
        self.payment.save(
            update_fields=[
                "method",
            ]
        )

        with self.assertRaises(ValidationError):
            validate_client_can_create_invoice(
                payment=self.payment,
            )

        with self.assertRaises(ValidationError):
            validate_manager_can_create_invoice(
                payment=self.payment,
            )

    # Проверяем защиту:
    # invoice нельзя создать для online payment.
    def test_cannot_create_invoice_for_online_payment(self):
        self.payment.method = PaymentMethod.ONLINE
        self.payment.save(
            update_fields=[
                "method",
            ]
        )

        with self.assertRaises(ValidationError):
            validate_client_can_create_invoice(
                payment=self.payment,
            )

        with self.assertRaises(ValidationError):
            validate_manager_can_create_invoice(
                payment=self.payment,
            )