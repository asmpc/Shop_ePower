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
)
from shop_epower.orders.models import OrderShipment, OrderStatus
from shop_epower.orders.tests.helpers import create_test_order


class TestsOrderShipmentModel(TestCase):
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
        self.debt_transaction = record_customer_debt(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment:model:debt:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

    # Отгрузка сохраняет связь с заказом, финансовым счётом
    # и операцией начисления полного обязательства.
    # Создание записи не начисляет долг повторно
    # и само по себе не меняет статус заказа.
    def test_shipment_links_order_to_debt_transaction(self):
        shipment = OrderShipment.objects.create(
            order=self.order,
            customer_account=self.account,
            debt_transaction=self.debt_transaction,
            total_amount=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
            created_by=self.manager,
        )

        shipment.refresh_from_db()

        self.assertEqual(shipment.order_id, self.order.pk)
        self.assertEqual(
            shipment.customer_account_id,
            self.account.pk,
        )
        self.assertEqual(
            shipment.debt_transaction_id,
            self.debt_transaction.pk,
        )
        self.assertEqual(
            shipment.total_amount,
            Decimal("100.00"),
        )
        self.assertEqual(
            shipment.currency_snapshot,
            self.order.currency_snapshot,
        )
        self.assertEqual(
            shipment.created_by_id,
            self.manager.pk,
        )
        self.assertIsNotNone(shipment.created_at)

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )

    # База данных запрещает вторую отгрузку одного заказа.
    # Используем разные финансовые операции, чтобы проверить
    # именно ограничение по заказу, а не уникальность операции долга.
    def test_order_cannot_have_two_shipments(self):
        OrderShipment.objects.create(
            order=self.order,
            customer_account=self.account,
            debt_transaction=self.debt_transaction,
            total_amount=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
            created_by=self.manager,
        )

        second_debt_transaction = record_customer_debt(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment:model:debt:002",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderShipment.objects.create(
                    order=self.order,
                    customer_account=self.account,
                    debt_transaction=second_debt_transaction,
                    total_amount=Decimal("100.00"),
                    currency_snapshot=self.order.currency_snapshot,
                    created_by=self.manager,
                )

        self.assertEqual(self.order.shipments.count(), 1)

    # База данных запрещает отгрузку
    # с нулевой или отрицательной суммой обязательства.
    def test_shipment_amount_must_be_positive(self):
        for amount in (Decimal("0.00"), Decimal("-10.00")):
            with self.subTest(amount=amount):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        OrderShipment.objects.create(
                            order=self.order,
                            customer_account=self.account,
                            debt_transaction=self.debt_transaction,
                            total_amount=amount,
                            currency_snapshot=self.order.currency_snapshot,
                            created_by=self.manager,
                        )

        self.assertEqual(self.order.shipments.count(), 0)

    # Одну операцию начисления долга нельзя использовать
    # для отгрузок двух разных заказов.
    def test_debt_transaction_cannot_be_reused(self):
        OrderShipment.objects.create(
            order=self.order,
            customer_account=self.account,
            debt_transaction=self.debt_transaction,
            total_amount=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
            created_by=self.manager,
        )
        second_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderShipment.objects.create(
                    order=second_order,
                    customer_account=self.account,
                    debt_transaction=self.debt_transaction,
                    total_amount=Decimal("100.00"),
                    currency_snapshot=second_order.currency_snapshot,
                    created_by=self.manager,
                )

        self.assertEqual(OrderShipment.objects.count(), 1)
        self.assertFalse(second_order.shipments.exists())
