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
    cancel_order_fund_assignment,
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

    # Поступления и назначения другого заказа не входят в сводку текущего.
    # Доступные средства показываются по общему финансовому счёту.
    def test_summary_excludes_other_order_receipts_and_assignments(self):
        other_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )

        record_manual_order_payment(
            order=other_order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="summary:other-order:receipt",
            created_by=self.manager,
        )

        assign_order_funds(
            order=other_order,
            amount=Decimal("40.00"),
            operation_key="summary:other-order:assignment",
            created_by=self.manager,
        )

        summary = get_order_financial_summary(order=self.order)

        self.assertEqual(
            summary["received_amount"],
            Decimal("0.00"),
        )
        self.assertEqual(
            summary["assigned_amount"],
            Decimal("0.00"),
        )
        self.assertEqual(
            summary["remaining_debt"],
            Decimal("0.00"),
        )
        self.assertEqual(
            summary["available_balance"],
            Decimal("60.00"),
        )

    # Долг отгруженного заказа не переносится в сводку другого заказа.
    # У второго заказа без отгрузки долг остаётся нулевым.
    def test_summary_excludes_debt_of_another_order(self):
        other_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )

        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )

        summary = get_order_financial_summary(order=other_order)

        self.assertEqual(
            summary["remaining_debt"],
            Decimal("0.00"),
        )
        self.assertEqual(
            summary["available_balance"],
            Decimal("0.00"),
        )

    # Отменённое назначение сохраняется в истории,
    # но исключается из суммы действующих назначений.
    # Доступные средства и долг после отгрузки восстанавливаются.
    def test_summary_excludes_cancelled_assignment_after_shipment(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="summary:cancel-assignment:receipt",
            created_by=self.manager,
        )

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="summary:cancel-assignment:assignment",
            created_by=self.manager,
        )

        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="summary:cancel-assignment:reversal",
            created_by=self.manager,
            comment="Funds were assigned to the wrong order.",
        )

        summary = get_order_financial_summary(order=self.order)

        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(
            summary["received_amount"],
            Decimal("100.00"),
        )
        self.assertEqual(
            summary["assigned_amount"],
            Decimal("0.00"),
        )
        self.assertEqual(
            summary["remaining_debt"],
            Decimal("100.00"),
        )
        self.assertEqual(
            summary["available_balance"],
            Decimal("100.00"),
        )

    # Полностью оплаченная отгрузка имеет нулевой долг.
    # Использованное назначение остаётся в сумме назначений,
    # а нераспределённый остаток доступен на счёте.
    def test_summary_for_fully_paid_shipped_order(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("120.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="summary:fully-paid:receipt",
            created_by=self.manager,
        )

        assign_order_funds(
            order=self.order,
            amount=Decimal("100.00"),
            operation_key="summary:fully-paid:assignment",
            created_by=self.manager,
        )

        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        summary = get_order_financial_summary(order=self.order)

        self.assertEqual(
            summary["received_amount"],
            Decimal("120.00"),
        )
        self.assertEqual(
            summary["assigned_amount"],
            Decimal("100.00"),
        )
        self.assertEqual(
            summary["remaining_debt"],
            Decimal("0.00"),
        )
        self.assertEqual(
            summary["available_balance"],
            Decimal("20.00"),
        )

    # До отгрузки назначенные деньги считаются предоплатой.
    # Назначение уменьшает доступный остаток, но не создаёт долг.
    def test_summary_before_shipment_has_no_debt(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="summary:before-shipment:receipt",
            created_by=self.manager,
        )

        assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="summary:before-shipment:assignment",
            created_by=self.manager,
        )

        summary = get_order_financial_summary(order=self.order)

        self.assertFalse(self.order.shipments.exists())
        self.assertEqual(
            summary["received_amount"],
            Decimal("100.00"),
        )
        self.assertEqual(
            summary["assigned_amount"],
            Decimal("60.00"),
        )
        self.assertEqual(
            summary["remaining_debt"],
            Decimal("0.00"),
        )
        self.assertEqual(
            summary["available_balance"],
            Decimal("40.00"),
        )
