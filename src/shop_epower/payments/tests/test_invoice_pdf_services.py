from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from reportlab.platypus import Paragraph

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import (
    DeliveryMethod,
    OrderItem,
    OrderStatus,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import (
    create_invoice_for_payment,
    generate_invoice_pdf,
)
from shop_epower.payments.tests.helpers import (
    create_test_company_settings,
    create_test_payment,
)


class TestsInvoicePdfServices(TestCase):

    def setUp(self):
        self.client_user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.order = create_test_order(
            user=self.client_user,
            status=OrderStatus.PROCESSING,
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

        create_test_company_settings(
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

        self.product = create_test_product()

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name="Original product",
            unit_price=Decimal("50.00"),
            quantity=2,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

    # Проверяем генерацию PDF:
    # сервис должен вернуть корректный PDF.
    def test_generate_invoice_pdf(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        pdf = generate_invoice_pdf(
            invoice=invoice,
        )

        self.assertIsInstance(
            pdf,
            bytes,
        )

        self.assertTrue(
            pdf.startswith(b"%PDF"),
        )

    # Проверяем содержимое PDF после изменения заказа:
    # документ использует название, количество и цену
    # из сохранённых строк Invoice.
    def test_pdf_uses_invoice_items_after_order_line_changes(self):
        invoice = create_invoice_for_payment(
            payment=self.payment,
        )

        OrderItem.objects.filter(
            pk=self.order_item.pk,
        ).update(
            product_name="Changed product",
            unit_price=Decimal("80.00"),
            quantity=1,
            total_price=Decimal("80.00"),
        )

        self.order.total_price = Decimal("80.00")
        self.order.save(
            update_fields=["total_price"],
        )

        with patch(
            "shop_epower.payments.services.invoice_pdf.Paragraph",
            wraps=Paragraph,
        ) as paragraph_spy:
            generate_invoice_pdf(
                invoice=invoice,
            )

        rendered_text = [
            call.args[0]
            for call in paragraph_spy.call_args_list
        ]

        self.assertIn("Original product", rendered_text)
        self.assertNotIn("Changed product", rendered_text)
        self.assertIn("2", rendered_text)
        self.assertIn(
            f"50.00 {invoice.currency_snapshot}",
            rendered_text,
        )