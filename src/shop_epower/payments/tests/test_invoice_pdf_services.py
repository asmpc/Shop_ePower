from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import (
    DeliveryMethod,
    Order, OrderStatus,
)
from shop_epower.payments.models import (
    CompanySettings,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import (
    create_invoice_for_payment,
    generate_invoice_pdf,
)

User = get_user_model()


class TestsInvoicePdfServices(TestCase):

    def setUp(self):
        self.client_user = User.objects.create_user(
            email="client@test.com",
            username="client",
            password="testpass123",
            role="client",
        )

        self.order = Order.objects.create(
            user=self.client_user,
            status=OrderStatus.PROCESSING,
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