from decimal import Decimal
from django.core.exceptions import ValidationError

from django.test import TestCase
from django.utils import timezone

from shop_epower.core.currency import get_base_currency
from shop_epower.payments.models import (
    Invoice,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    CompanySettings,
)
from shop_epower.payments.tests.helpers import (
    create_test_company_settings,
    create_test_payment,
)

from shop_epower.payments.services import (
    generate_invoice_number,
    create_invoice_for_payment,
    cancel_invoice,
)

from shop_epower.orders.models import (
    OrderStatus,
    DeliveryMethod,
)
from shop_epower.orders.tests.helpers import create_test_order

from shop_epower.accounts.tests.helpers import (
    create_test_user,
    create_test_admin,
)



class TestsInvoiceServices(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.admin = create_test_admin(
            email="admin@test.com",
            username="admin",
            password="testpass123",
        )

        self.order = create_test_order(
            user=self.user,
            status=OrderStatus.PROCESSING,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="+375291112233",
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

    # Проверяем генерацию первого номера счета:
    # если счетов за текущий год еще нет,
    # номер должен начинаться с 000001.
    def test_generate_first_invoice_number_for_current_year(self):
        current_year = timezone.now().year

        invoice_number = generate_invoice_number()

        self.assertEqual(
            invoice_number,
            f"INV-{current_year}-000001",
        )

    # Проверяем последовательную генерацию номера счета:
    # следующий счет должен получить следующий номер.
    def test_generate_next_invoice_number_for_current_year(self):
        current_year = timezone.now().year

        Invoice.objects.create(
            order=self.order,
            payment=self.payment,
            invoice_number=f"INV-{current_year}-000001",

            seller_company_name="Shop ePower LLC",
            seller_tax_id="123456789",
            seller_legal_address="Seller legal address",
            seller_bank_name="Seller Bank",
            seller_bank_account="BY00 TEST 0000 0000 0000 0000 0000",

            buyer_name="Test Client",
            buyer_email="client@test.com",

            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        invoice_number = generate_invoice_number()

        self.assertEqual(
            invoice_number,
            f"INV-{current_year}-000002",
        )

    # Проверяем создание invoice из payment:
    # сервис должен создать счет со snapshot продавца,
    # покупателя, суммы и валюты.
    def test_create_invoice_for_payment(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        self.assertEqual(
            invoice.payment,
            self.payment,
        )

        self.assertEqual(
            invoice.order,
            self.order,
        )

        self.assertEqual(
            invoice.seller_company_name,
            "Shop ePower LLC",
        )

        self.assertEqual(
            invoice.seller_tax_id,
            "123456789",
        )

        self.assertEqual(
            invoice.buyer_name,
            "Test Client",
        )

        self.assertEqual(
            invoice.buyer_email,
            "client@test.com",
        )

        self.assertEqual(
            invoice.amount,
            self.payment.amount,
        )

        self.assertEqual(
            invoice.currency_snapshot,
            self.payment.currency_snapshot,
        )

    # Проверяем генерацию номера invoice:
    # созданный счет должен получить номер в формате INV-YYYY-000001.
    def test_create_invoice_for_payment_generates_invoice_number(self):
        current_year = timezone.now().year

        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        self.assertEqual(
            invoice.invoice_number,
            f"INV-{current_year}-000001",
        )

    # Проверяем бизнес-правило:
    # invoice можно создать только для оплаты по счету.
    def test_cannot_create_invoice_for_non_invoice_payment(self):
        self.payment.method = PaymentMethod.ON_RECEIPT
        self.payment.save(
            update_fields=[
                "method",
            ]
        )

        with self.assertRaises(ValidationError):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем защиту от дублей:
    # для одного payment нельзя создать два invoice.
    def test_cannot_create_duplicate_invoice_for_payment(self):
        create_invoice_for_payment(
            payment=self.payment,
        )

        with self.assertRaises(ValidationError):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем защиту:
    # invoice нельзя создать без реквизитов нашей компании.
    def test_cannot_create_invoice_without_company_settings(self):
        CompanySettings.objects.all().delete()

        with self.assertRaises(ValidationError):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем защиту:
    # invoice нельзя создать без имени клиента.
    def test_cannot_create_invoice_without_customer_name(self):
        self.order.customer_name = ""
        self.order.save(
            update_fields=[
                "customer_name",
            ]
        )

        with self.assertRaises(ValidationError):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем защиту:
    # invoice нельзя создать без email клиента.
    def test_cannot_create_invoice_without_customer_email(self):
        self.order.customer_email = ""
        self.order.save(
            update_fields=[
                "customer_email",
            ]
        )

        with self.assertRaises(ValidationError):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем защиту:
    # invoice нельзя создать без телефона клиента.
    def test_cannot_create_invoice_without_customer_phone(self):
        self.order.customer_phone = ""
        self.order.save(
            update_fields=[
                "customer_phone",
            ]
        )

        with self.assertRaises(ValidationError):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем защиту для юрлица:
    # invoice нельзя создать без УНП / ИНН.
    def test_cannot_create_legal_entity_invoice_without_tax_id(self):
        self.order.is_legal_entity = True
        self.order.company_name = "Test Company"
        self.order.tax_id = ""
        self.order.legal_address = "Test legal address"

        self.order.save(
            update_fields=[
                "is_legal_entity",
                "company_name",
                "tax_id",
                "legal_address",
            ]
        )

        with self.assertRaises(ValidationError):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем отмену invoice:
    # сервис должен изменить статус и сохранить
    # информацию об отмене.
    def test_cancel_invoice(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        from shop_epower.payments.services import (
            cancel_invoice,
        )

        cancel_invoice(
            invoice=invoice,
            cancelled_by=self.admin,
            comment="Wrong customer data",
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.status,
            "cancelled",
        )

        self.assertEqual(
            invoice.cancel_comment,
            "Wrong customer data",
        )

        self.assertEqual(
            invoice.cancelled_by,
            self.admin,
        )

        self.assertIsNotNone(
            invoice.cancelled_at,
        )

    # Проверяем защиту:
    # повторно отменить invoice нельзя.
    def test_cannot_cancel_invoice_twice(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        from shop_epower.payments.services import (
            cancel_invoice,
        )

        cancel_invoice(
            invoice=invoice,
            cancelled_by=self.admin,
            comment="First cancellation",
        )

        with self.assertRaises(ValidationError):
            cancel_invoice(
                invoice=invoice,
                cancelled_by=self.admin,
                comment="Second cancellation",
            )

    # Проверяем бизнес-правило:
    # invoice нельзя отменить без комментария.
    def test_cannot_cancel_invoice_without_comment(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        with self.assertRaises(ValidationError):
            cancel_invoice(
                invoice=invoice,
                cancelled_by=self.admin,
                comment="",
            )

    # Проверяем, что Invoice нельзя создать
    # для заказа, который ещё не переведён в processing.
    def test_create_invoice_for_new_order_raises_error(self):
        self.order.status = OrderStatus.NEW
        self.order.save(
            update_fields=['status'],
        )

        with self.assertRaisesMessage(
                ValidationError,
                'Invoice can be generated only for an order in processing.',
        ):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем, что Invoice нельзя создать
    # для доставки без выбранного провайдера.
    def test_create_invoice_for_shipping_without_provider_raises_error(self):

        self.order.delivery_method = DeliveryMethod.SHIPPING
        self.order.delivery_provider = ''
        self.order.delivery_address = 'Test address'
        self.order.delivery_cost = Decimal('10.00')
        self.order.save(
            update_fields=[
                'delivery_method',
                'delivery_provider',
                'delivery_address',
                'delivery_cost',
            ],
        )

        with self.assertRaisesMessage(
            ValidationError,
            'Delivery provider must be selected before generating invoice.',
        ):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем, что Invoice нельзя создать
    # для доставки без указанного адреса.
    def test_create_invoice_for_shipping_without_address_raises_error(self):

        self.order.delivery_method = DeliveryMethod.SHIPPING
        self.order.delivery_provider = 'post'
        self.order.delivery_address = ''
        self.order.delivery_cost = Decimal('10.00')
        self.order.save(
            update_fields=[
                'delivery_method',
                'delivery_provider',
                'delivery_address',
                'delivery_cost',
            ],
        )

        with self.assertRaisesMessage(
            ValidationError,
            'Delivery address must be specified before generating invoice.',
        ):
            create_invoice_for_payment(
                payment=self.payment,
            )

    # Проверяем, что Invoice нельзя создать
    # для доставки без рассчитанной стоимости.
    def test_create_invoice_for_shipping_without_cost_raises_error(self):

        self.order.delivery_method = DeliveryMethod.SHIPPING
        self.order.delivery_provider = 'post'
        self.order.delivery_address = 'Test address'
        self.order.delivery_cost = None
        self.order.save(
            update_fields=[
                'delivery_method',
                'delivery_provider',
                'delivery_address',
                'delivery_cost',
            ],
        )

        with self.assertRaisesMessage(
            ValidationError,
            'Delivery cost must be calculated before generating invoice.',
        ):
            create_invoice_for_payment(
                payment=self.payment,
            )