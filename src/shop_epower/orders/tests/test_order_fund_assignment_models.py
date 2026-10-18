from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import AccountTransactionActorType
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_deposit,
    record_customer_funds_assignment,
)
from shop_epower.orders.models import (
    OrderFundAssignment,
    OrderFundAssignmentSource,
)
from shop_epower.orders.tests.helpers import create_test_order


class TestsOrderFundAssignmentModel(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
        )

        self.deposit_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="assignment:model:deposit:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        self.account_transaction = record_customer_funds_assignment(
            account=self.account,
            amount=Decimal("60.00"),
            operation_key="assignment:model:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

    # Назначение связывает заказ с финансовой операцией и суммой.
    # Создание этой связи не списывает средства повторно.
    def test_assignment_links_order_to_financial_transaction(self):
        assignment = OrderFundAssignment.objects.create(
            order=self.order,
            account_transaction=self.account_transaction,
            amount=Decimal("60.00"),
        )

        self.assertEqual(assignment.order_id, self.order.pk)
        self.assertEqual(
            assignment.account_transaction_id,
            self.account_transaction.pk,
        )
        self.assertEqual(assignment.amount, Decimal("60.00"))

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Одну финансовую операцию нельзя использовать
    # для назначения средств сразу на два заказа.
    def test_financial_transaction_cannot_be_reused(self):
        second_order = create_test_order(
            user=self.user,
            customer_account=self.account,
        )
        OrderFundAssignment.objects.create(
            order=self.order,
            account_transaction=self.account_transaction,
            amount=Decimal("60.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderFundAssignment.objects.create(
                    order=second_order,
                    account_transaction=self.account_transaction,
                    amount=Decimal("60.00"),
                )

        self.assertEqual(OrderFundAssignment.objects.count(), 1)
        self.assertFalse(second_order.fund_assignments.exists())

    # База данных запрещает создание назначения
    # с нулевой или отрицательной суммой.
    def test_assignment_amount_must_be_positive(self):
        for amount in (Decimal("0.00"), Decimal("-10.00")):
            with self.subTest(amount=amount):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        OrderFundAssignment.objects.create(
                            order=self.order,
                            account_transaction=self.account_transaction,
                            amount=amount,
                        )

        self.assertEqual(OrderFundAssignment.objects.count(), 0)

    # Одно поступление нельзя дважды указать
    # в источниках одного назначения.
    def test_assignment_cannot_repeat_same_deposit_source(self):
        assignment = OrderFundAssignment.objects.create(
            order=self.order,
            account_transaction=self.account_transaction,
            amount=Decimal("60.00"),
        )
        OrderFundAssignmentSource.objects.create(
            assignment=assignment,
            deposit_transaction=self.deposit_transaction,
            amount=Decimal("60.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderFundAssignmentSource.objects.create(
                    assignment=assignment,
                    deposit_transaction=self.deposit_transaction,
                    amount=Decimal("60.00"),
                )

        self.assertEqual(assignment.sources.count(), 1)

    # Источник связывает назначение с конкретным поступлением.
    # Сохранение этой связи не списывает средства повторно.
    def test_assignment_source_links_to_deposit(self):
        assignment = OrderFundAssignment.objects.create(
            order=self.order,
            account_transaction=self.account_transaction,
            amount=Decimal("60.00"),
        )

        source = OrderFundAssignmentSource.objects.create(
            assignment=assignment,
            deposit_transaction=self.deposit_transaction,
            amount=Decimal("60.00"),
        )

        self.assertEqual(source.assignment_id, assignment.pk)
        self.assertEqual(
            source.deposit_transaction_id,
            self.deposit_transaction.pk,
        )
        self.assertEqual(source.amount, Decimal("60.00"))
        self.assertEqual(assignment.sources.count(), 1)

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )

    # База данных запрещает источник назначения
    # с нулевой или отрицательной суммой.
    def test_assignment_source_amount_must_be_positive(self):
        assignment = OrderFundAssignment.objects.create(
            order=self.order,
            account_transaction=self.account_transaction,
            amount=Decimal("60.00"),
        )

        for amount in (Decimal("0.00"), Decimal("-10.00")):
            with self.subTest(amount=amount):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        OrderFundAssignmentSource.objects.create(
                            assignment=assignment,
                            deposit_transaction=self.deposit_transaction,
                            amount=amount,
                        )

        self.assertEqual(assignment.sources.count(), 0)
