from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import InvoiceStatus, PaymentMethod
from shop_epower.payments.tests.helpers import (
    create_test_invoice,
    create_test_payment,
)


class TestsCustomerOrderDetailViews(TestCase):
    # Проверяем показ нескольких платежей в карточке заказа:
    # клиент видит каждый платёж со своим номером и суммой.
    def test_customer_order_detail_shows_all_payments(self):
        user = create_test_user()
        account = create_personal_customer_account(user=user)
        order = create_test_order(
            user=user,
            customer_account=account,
            total_price=Decimal("100.00"),
        )
        first_payment = create_test_payment(
            order=order,
            amount=Decimal("40.00"),
        )
        second_payment = create_test_payment(
            order=order,
            amount=Decimal("60.00"),
        )

        self.client.force_login(user)
        response = self.client.get(
            reverse("orders:detail", args=[order.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Payment #{first_payment.pk}")
        self.assertContains(response, f"Payment #{second_payment.pk}")
        self.assertContains(response, "40.00")
        self.assertContains(response, "60.00")

    # Проверяем показ счёта при нескольких платежах заказа:
    # клиент видит номер выставленного счёта и ссылку на PDF.
    def test_order_detail_shows_invoice_with_multiple_payments(self):
        user = create_test_user()
        account = create_personal_customer_account(user=user)
        order = create_test_order(
            user=user,
            customer_account=account,
            total_price=Decimal("100.00"),
        )
        first_payment = create_test_payment(
            order=order,
            amount=Decimal("40.00"),
        )
        create_test_payment(
            order=order,
            amount=Decimal("60.00"),
        )
        invoice = create_test_invoice(
            order=order,
            payment=first_payment,
            amount=order.total_price,
        )

        self.client.force_login(user)
        response = self.client.get(
            reverse("orders:detail", args=[order.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, invoice.invoice_number)
        self.assertContains(
            response,
            f'href="{reverse("payments:client_invoice_pdf", args=[invoice.pk])}"',
        )

    # Проверяем карточку заказа после перевыпуска счёта:
    # действующим документом становится новый Invoice,
    # аннулированный остаётся в истории.
    # Наличие платежа для отображения счёта не требуется.
    def test_order_detail_shows_current_invoice_after_reissue(self):
        user = create_test_user()
        account = create_personal_customer_account(user=user)

        order = create_test_order(
            user=user,
            customer_account=account,
            status=OrderStatus.PROCESSING,
            payment_method=PaymentMethod.INVOICE,
        )

        create_test_invoice(
            order=order,
            payment=None,
            invoice_number="INV-2026-000001",
            status=InvoiceStatus.CANCELLED,
        )

        current_invoice = create_test_invoice(
            order=order,
            payment=None,
            invoice_number="INV-2026-000002",
            status=InvoiceStatus.ISSUED,
        )

        self.client.force_login(user)

        response = self.client.get(
            reverse("orders:detail", args=[order.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["invoice"],
            current_invoice,
        )
        self.assertTrue(response.context["invoice_required"])
        self.assertContains(response, current_invoice.invoice_number)
        self.assertFalse(order.payments.exists())