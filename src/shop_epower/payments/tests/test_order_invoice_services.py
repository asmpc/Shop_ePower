from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import (
    OrderItem,
    OrderStatus,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    InvoiceItem,
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

    # Проверяем перевыпуск после аннулирования и изменения заказа:
    # старый счёт сохраняет исходные строки и сумму,
    # новый получает обновлённые позиции и отдельный номер.
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

        old_item = first_invoice.items.get()
        new_item = new_invoice.items.get()

        self.assertEqual(old_item.product_name, "Original product")
        self.assertEqual(old_item.unit_price, Decimal("50.00"))
        self.assertEqual(old_item.quantity, 2)
        self.assertEqual(old_item.total_price, Decimal("100.00"))
        self.assertEqual(first_invoice.amount, Decimal("100.00"))

        self.assertEqual(new_item.product_name, "Changed product")
        self.assertEqual(new_item.unit_price, Decimal("80.00"))
        self.assertEqual(new_item.quantity, 1)
        self.assertEqual(new_item.total_price, Decimal("80.00"))
        self.assertEqual(new_invoice.amount, Decimal("80.00"))

    # Проверяем независимость выписанного счёта:
    # изменение названия, цены и количества в заказе
    # не меняет сохранённые строки и сумму Invoice.
    def test_invoice_preserves_items_after_order_line_changes(self):
        invoice = create_invoice_for_order(
            order=self.order,
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

        invoice.refresh_from_db()
        item = invoice.items.get()

        self.assertEqual(item.product_name, "Original product")
        self.assertEqual(item.unit_price, Decimal("50.00"))
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.total_price, Decimal("100.00"))
        self.assertEqual(
            item.currency_snapshot,
            self.order.currency_snapshot,
        )
        self.assertEqual(invoice.amount, Decimal("100.00"))

    # Проверяем целостность выписки:
    # ошибка после сохранения первой строки откатывает
    # и строки счёта, и сам Invoice.
    def test_invoice_creation_rolls_back_when_item_saving_fails(self):
        def save_one_item_and_fail(items):
            items[0].save()
            raise RuntimeError("Invoice item saving failed.")

        with patch(
            "shop_epower.payments.services.invoice.InvoiceItem.objects.bulk_create",
            side_effect=save_one_item_and_fail,
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Invoice item saving failed.",
            ):
                create_invoice_for_order(
                    order=self.order,
                )

        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(InvoiceItem.objects.exists())
