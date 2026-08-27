from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_user
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
from shop_epower.payments.tests.helpers import create_test_payment
from shop_epower.payments.validators import (
    validate_client_can_create_invoice,
    validate_manager_can_create_invoice,
)


class TestsInvoiceValidators(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.order = create_test_order(
            user=self.user,
            status=OrderStatus.NEW,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="+375291112233",
            delivery_method=DeliveryMethod.PICKUP,
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

    def prepare_shipping_order(
        self,
        *,
        status=OrderStatus.PROCESSING,
        delivery_provider="post",
        delivery_address="Minsk, Main street, 10",
        delivery_cost=Decimal("20.00"),
    ):
        self.order.delivery_method = DeliveryMethod.SHIPPING
        self.order.status = status
        self.order.delivery_provider = delivery_provider
        self.order.delivery_address = delivery_address
        self.order.delivery_cost = delivery_cost

        self.order.save(
            update_fields=[
                "delivery_method",
                "status",
                "delivery_provider",
                "delivery_address",
                "delivery_cost",
            ]
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
        self.prepare_shipping_order()

        with self.assertRaises(ValidationError):
            validate_client_can_create_invoice(
                payment=self.payment,
            )

    # Проверяем правило для менеджера:
    # менеджер может создать invoice для доставки,
    # если заказ находится в обработке
    # и параметры доставки заполнены.
    def test_manager_can_create_invoice_for_shipping_order(self):
        self.prepare_shipping_order()

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
            seller_bank_account=(
                "BY00 TEST 0000 0000 0000 0000 0000"
            ),

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

    # Проверяем manager workflow:
    # invoice нельзя создать, пока заказ
    # не переведён в обработку.
    def test_manager_cannot_create_invoice_for_new_order(self):
        with self.assertRaises(ValidationError):
            validate_manager_can_create_invoice(
                payment=self.payment,
            )

    # Проверяем manager workflow:
    # invoice нельзя создать для shipping,
    # пока не выбран delivery provider.
    def test_manager_cannot_create_invoice_without_delivery_provider(self):
        self.prepare_shipping_order(
            delivery_provider="",
        )

        with self.assertRaises(ValidationError):
            validate_manager_can_create_invoice(
                payment=self.payment,
            )

    # Проверяем manager workflow:
    # invoice нельзя создать для shipping,
    # пока не указан адрес доставки.
    def test_manager_cannot_create_invoice_without_delivery_address(self):
        self.prepare_shipping_order(
            delivery_address="",
        )

        with self.assertRaises(ValidationError):
            validate_manager_can_create_invoice(
                payment=self.payment,
            )

    # Проверяем manager workflow:
    # invoice нельзя создать для shipping,
    # пока стоимость доставки не рассчитана.
    def test_manager_cannot_create_invoice_without_delivery_cost(self):
        self.prepare_shipping_order(
            delivery_cost=None,
        )

        with self.assertRaises(ValidationError):
            validate_manager_can_create_invoice(
                payment=self.payment,
            )

    # Проверяем бесплатную доставку:
    # рассчитанная стоимость 0.00 является валидным значением.
    def test_manager_can_create_invoice_with_free_delivery(self):
        self.prepare_shipping_order(
            delivery_cost=Decimal("0.00"),
        )

        validate_manager_can_create_invoice(
            payment=self.payment,
        )