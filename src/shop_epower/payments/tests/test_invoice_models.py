from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.core.currency import get_base_currency
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    InvoiceStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.tests.helpers import create_test_payment


class TestsInvoiceModel(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.order = create_test_order(
            user=self.user,
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

    # Проверяем связи Invoice:
    # счет должен быть связан с заказом и payment.
    def test_invoice_relations(self):
        self.assertEqual(
            self.invoice.order,
            self.order,
        )

        self.assertEqual(
            self.invoice.payment,
            self.payment,
        )

    # Проверяем номер счета:
    # invoice_number должен сохраняться для PDF и поиска.
    def test_invoice_number(self):
        self.assertEqual(
            self.invoice.invoice_number,
            "INV-2026-000001",
        )

    # Проверяем snapshot продавца:
    # реквизиты компании должны сохраняться в Invoice
    # независимо от будущих изменений CompanySettings.
    def test_invoice_stores_seller_snapshot(self):
        self.assertEqual(
            self.invoice.seller_company_name,
            "Shop ePower LLC",
        )

        self.assertEqual(
            self.invoice.seller_tax_id,
            "123456789",
        )

        self.assertEqual(
            self.invoice.seller_bank_name,
            "Seller Bank",
        )

        self.assertEqual(
            self.invoice.seller_bank_account,
            "BY00 TEST 0000 0000 0000 0000 0000",
        )

    # Проверяем snapshot покупателя:
    # данные клиента должны сохраняться в Invoice
    # на момент выставления счета.
    def test_invoice_stores_buyer_snapshot(self):
        self.assertEqual(
            self.invoice.buyer_name,
            "Test Client",
        )

        self.assertEqual(
            self.invoice.buyer_email,
            "client@test.com",
        )

        self.assertEqual(
            self.invoice.buyer_phone,
            "+375291112233",
        )

        self.assertFalse(
            self.invoice.buyer_is_legal_entity,
        )

    # Проверяем сумму и валюту счета.
    def test_invoice_stores_amount_and_currency(self):
        self.assertEqual(
            self.invoice.amount,
            Decimal("100.00"),
        )

        self.assertEqual(
            self.invoice.currency_snapshot,
            get_base_currency(),
        )

    # Проверяем строковое представление счета.
    def test_invoice_str(self):
        self.assertEqual(
            str(self.invoice),
            "Invoice INV-2026-000001 for Order #"
            f"{self.order.id}",
        )

    # Проверяем статус invoice по умолчанию:
    # новый счет должен создаваться в статусе ISSUED.
    def test_invoice_default_status_is_issued(self):
        self.assertEqual(
            self.invoice.status,
            InvoiceStatus.ISSUED,
        )

    # Проверяем поля отмены invoice:
    # новый счет не должен иметь данных отмены.
    def test_invoice_cancel_fields_are_empty_by_default(self):
        self.assertEqual(
            self.invoice.cancel_comment,
            "",
        )

        self.assertIsNone(
            self.invoice.cancelled_at,
        )

        self.assertIsNone(
            self.invoice.cancelled_by,
        )

