from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import AccountTransactionActorType
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_deposit,
)
from shop_epower.orders.selectors import get_order_fund_assignments
from shop_epower.orders.services import (
    assign_order_funds,
    cancel_order_fund_assignment,
)
from shop_epower.orders.tests.helpers import create_test_order


class TestsOrderFundAssignmentSelectors(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
        )
        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="assignment:selector:deposit:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

    # История выбранного заказа не включает назначения
    # других заказов того же клиента и финансового счёта.
    def test_returns_assignments_only_for_selected_order(self):
        selected_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:selector:selected",
            created_by=self.manager,
        )
        other_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
        )
        assign_order_funds(
            order=other_order,
            amount=Decimal("40.00"),
            operation_key="assignment:selector:other",
            created_by=self.manager,
        )

        assignments = get_order_fund_assignments(
            order=self.order,
        )

        self.assertEqual(
            list(assignments),
            [selected_assignment],
        )

    # История сохраняет действующие и отменённые назначения.
    # Более новое назначение показывается первым.
    def test_returns_active_and_cancelled_assignments_newest_first(self):
        cancelled_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:selector:cancelled",
            created_by=self.manager,
        )
        cancel_order_fund_assignment(
            assignment=cancelled_assignment,
            operation_key="assignment:selector:cancel",
            created_by=self.manager,
            comment="Incorrect assignment amount.",
        )
        active_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("40.00"),
            operation_key="assignment:selector:active",
            created_by=self.manager,
        )

        assignments = get_order_fund_assignments(
            order=self.order,
        )

        self.assertEqual(
            list(assignments),
            [
                active_assignment,
                cancelled_assignment,
            ],
        )
