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
    record_customer_debt,
    record_customer_deposit,
    record_customer_funds_application,
)
from shop_epower.orders.models import (
    OrderFundApplication,
    OrderShipment,
    OrderStatus,
)
from shop_epower.orders.services import assign_order_funds
from shop_epower.orders.tests.helpers import create_test_order


class TestsOrderFundApplicationModel(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )
        self.deposit_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="fund-application:model:deposit",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        self.assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="fund-application:model:assignment",
            created_by=self.manager,
        )
        self.debt_transaction = record_customer_debt(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="fund-application:model:debt",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )
        self.shipment = OrderShipment.objects.create(
            order=self.order,
            customer_account=self.account,
            debt_transaction=self.debt_transaction,
            total_amount=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
            created_by=self.manager,
        )
        self.application_transaction = record_customer_funds_application(
            account=self.account,
            amount=Decimal("60.00"),
            operation_key="fund-application:model:application",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

    # Применение связывает назначение, отгрузку и финансовую операцию.
    # Сохранение этой связи не уменьшает балансы повторно.
    def test_application_links_assignment_shipment_and_transaction(self):
        application = OrderFundApplication.objects.create(
            assignment=self.assignment,
            shipment=self.shipment,
            account_transaction=self.application_transaction,
            amount=Decimal("60.00"),
        )

        application.refresh_from_db()

        self.assertEqual(
            application.assignment_id,
            self.assignment.pk,
        )
        self.assertEqual(
            application.shipment_id,
            self.shipment.pk,
        )
        self.assertEqual(
            application.account_transaction_id,
            self.application_transaction.pk,
        )
        self.assertEqual(
            application.amount,
            Decimal("60.00"),
        )
        self.assertIsNotNone(application.created_at)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)

    # База данных запрещает применение средств с нулевой суммой.
    # Неудачная вставка не оставляет записи применения.
    def test_application_rejects_zero_amount(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderFundApplication.objects.create(
                    assignment=self.assignment,
                    shipment=self.shipment,
                    account_transaction=self.application_transaction,
                    amount=Decimal("0.00"),
                )

        self.assertFalse(
            OrderFundApplication.objects.exists(),
        )

    # Одну финансовую операцию нельзя связать
    # с двумя записями применения средств.
    def test_application_transaction_cannot_be_reused(self):
        OrderFundApplication.objects.create(
            assignment=self.assignment,
            shipment=self.shipment,
            account_transaction=self.application_transaction,
            amount=Decimal("60.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderFundApplication.objects.create(
                    assignment=self.assignment,
                    shipment=self.shipment,
                    account_transaction=self.application_transaction,
                    amount=Decimal("60.00"),
                )

        self.assertEqual(
            OrderFundApplication.objects.count(),
            1,
        )
