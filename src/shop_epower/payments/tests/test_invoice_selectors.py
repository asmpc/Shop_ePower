from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import InvoiceStatus
from shop_epower.payments.selectors import get_invoices_for_order
from shop_epower.payments.tests.helpers import create_test_invoice


class TestsInvoiceSelectors(TestCase):
    # История содержит действующий и аннулированный Invoice заказа.
    # Документы другого заказа не попадают в результат.
    def test_get_invoices_for_order_returns_only_selected_order(self):
        user = create_test_user()
        order = create_test_order(user=user)
        other_order = create_test_order(user=user)

        cancelled_invoice = create_test_invoice(
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
        create_test_invoice(
            order=other_order,
            payment=None,
            invoice_number="INV-2026-000003",
            status=InvoiceStatus.ISSUED,
        )

        self.assertEqual(
            list(get_invoices_for_order(order=order)),
            [current_invoice, cancelled_invoice],
        )