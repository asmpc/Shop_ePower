from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)
from shop_epower.payments.services import (
    cancel_invoice,
    create_invoice_for_order,
)
from shop_epower.payments.tests.helpers import create_test_company_settings


class TestsOrderInvoiceServices(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.account = create_personal_customer_account(user=self.user)

        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            payment_method=PaymentMethod.INVOICE,
            total_price=Decimal("100.00"),
        )

        self.company_settings = create_test_company_settings()

    # Проверяем выставление счёта до получения денег:
    # документ сохраняет данные заказа и реквизиты продавца.
    # Платёж и финансовые операции не создаются,
    # балансы и состояние выполнения заказа не меняются.
    def test_create_invoice_for_order_without_payment(self):
        invoice = create_invoice_for_order(
            order=self.order,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(invoice.order, self.order)
        self.assertIsNone(invoice.payment_id)
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, self.order.total_price)
        self.assertEqual(
            invoice.currency_snapshot,
            self.order.currency_snapshot,
        )
        self.assertEqual(
            invoice.seller_company_name,
            self.company_settings.company_name,
        )
        self.assertEqual(
            invoice.buyer_name,
            self.order.customer_name,
        )

        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(self.account.transactions.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.PROCESSING)

    # Проверяем запрет второго действующего счёта:
    # пока первый Invoice не аннулирован, новый выставить нельзя.
    # Существующий документ сохраняется без изменений.
    def test_cannot_create_invoice_while_issued_invoice_exists(self):
        first_invoice = create_invoice_for_order(
            order=self.order,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "An issued invoice already exists for this order.",
        ):
            create_invoice_for_order(
                order=self.order,
            )

        first_invoice.refresh_from_db()

        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(first_invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(self.account.transactions.count(), 0)

    # Проверяем перевыпуск после аннулирования:
    # старый счёт и сведения об аннулировании сохраняются.
    # Новый счёт получает отдельную запись и другой номер.
    # Получение денег и балансы этот процесс не затрагивает.
    def test_can_create_new_invoice_after_previous_is_cancelled(self):
        manager = create_test_manager()
        reason = "Invoice requires correction."

        first_invoice = create_invoice_for_order(
            order=self.order,
        )
        original_number = first_invoice.invoice_number

        cancel_invoice(
            invoice=first_invoice,
            cancelled_by=manager,
            comment=reason,
        )

        new_invoice = create_invoice_for_order(
            order=self.order,
        )

        first_invoice.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            Invoice.objects.filter(order=self.order).count(),
            2,
        )
        self.assertNotEqual(new_invoice.pk, first_invoice.pk)
        self.assertNotEqual(
            new_invoice.invoice_number,
            original_number,
        )
        self.assertEqual(first_invoice.invoice_number, original_number)
        self.assertEqual(first_invoice.status, InvoiceStatus.CANCELLED)
        self.assertEqual(first_invoice.cancelled_by, manager)
        self.assertEqual(first_invoice.cancel_comment, reason)
        self.assertIsNotNone(first_invoice.cancelled_at)

        self.assertEqual(new_invoice.status, InvoiceStatus.ISSUED)
        self.assertIsNone(new_invoice.payment_id)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(self.account.transactions.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
