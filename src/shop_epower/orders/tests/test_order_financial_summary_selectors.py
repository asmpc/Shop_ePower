from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderItem, OrderStatus
from shop_epower.orders.selectors import get_order_financial_summary
from shop_epower.orders.services import (
    assign_order_funds,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.choices import PaymentMethod
from shop_epower.payments.services import record_manual_order_payment


class TestsOrderFinancialSummarySelectors(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )

        product = create_test_product()
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

    # Проверяем сводку частично оплаченного отгруженного заказа:
    # поступило 150, назначено 90, долг заказа — 10,
    # доступный остаток счёта — 60.
    def test_summary_for_partially_paid_shipped_order(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("150.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="order:summary:receipt",
            created_by=self.manager,
        )

        assign_order_funds(
            order=self.order,
            amount=Decimal("90.00"),
            operation_key="order:summary:assignment",
            created_by=self.manager,
        )

        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        summary = get_order_financial_summary(order=self.order)

        self.assertEqual(summary["received_amount"], Decimal("150.00"))
        self.assertEqual(summary["assigned_amount"], Decimal("90.00"))
        self.assertEqual(summary["remaining_debt"], Decimal("10.00"))
        self.assertEqual(summary["available_balance"], Decimal("60.00"))
        self.assertEqual(summary["currency"], self.account.currency)
