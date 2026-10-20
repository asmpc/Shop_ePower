from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.models import AccountTransactionActorType
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_debt,
)
from shop_epower.orders.models import (
    OrderItem,
    OrderShipment,
    OrderShipmentItem,
    OrderStatus,
)
from shop_epower.orders.tests.helpers import create_test_order


class TestsOrderShipmentItemModel(TestCase):
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
        self.product = create_test_product()
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("50.00"),
            quantity=2,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )
        self.debt_transaction = record_customer_debt(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment-item:model:debt:001",
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

    # Позиция отгрузки сохраняет связь с исходной позицией заказа
    # и отдельные снимки названия, цены, количества, суммы и валюты.
    def test_shipment_item_stores_order_item_snapshots(self):
        shipment_item = OrderShipmentItem.objects.create(
            shipment=self.shipment,
            order_item=self.order_item,
            product_name=self.order_item.product_name,
            unit_price=self.order_item.unit_price,
            quantity=self.order_item.quantity,
            total_price=self.order_item.total_price,
            currency_snapshot=self.order_item.currency_snapshot,
        )

        shipment_item.refresh_from_db()

        self.assertEqual(
            shipment_item.shipment_id,
            self.shipment.pk,
        )
        self.assertEqual(
            shipment_item.order_item_id,
            self.order_item.pk,
        )
        self.assertEqual(
            shipment_item.product_name,
            self.product.name,
        )
        self.assertEqual(
            shipment_item.unit_price,
            Decimal("50.00"),
        )
        self.assertEqual(shipment_item.quantity, 2)
        self.assertEqual(
            shipment_item.total_price,
            Decimal("100.00"),
        )
        self.assertEqual(
            shipment_item.currency_snapshot,
            self.order.currency_snapshot,
        )

    # Изменение исходной позиции заказа не меняет
    # исторические название, цену, количество и сумму отгрузки.
    def test_shipment_item_snapshots_do_not_follow_order_item_changes(self):
        shipment_item = OrderShipmentItem.objects.create(
            shipment=self.shipment,
            order_item=self.order_item,
            product_name=self.order_item.product_name,
            unit_price=self.order_item.unit_price,
            quantity=self.order_item.quantity,
            total_price=self.order_item.total_price,
            currency_snapshot=self.order_item.currency_snapshot,
        )

        self.order_item.product_name = "Changed product"
        self.order_item.unit_price = Decimal("80.00")
        self.order_item.quantity = 3
        self.order_item.total_price = Decimal("240.00")
        self.order_item.save(
            update_fields=[
                "product_name",
                "unit_price",
                "quantity",
                "total_price",
            ],
        )

        shipment_item.refresh_from_db()

        self.assertEqual(
            shipment_item.product_name,
            self.product.name,
        )
        self.assertEqual(
            shipment_item.unit_price,
            Decimal("50.00"),
        )
        self.assertEqual(shipment_item.quantity, 2)
        self.assertEqual(
            shipment_item.total_price,
            Decimal("100.00"),
        )

    # База данных запрещает позицию отгрузки
    # с нулевым количеством товара.
    def test_shipment_item_rejects_zero_quantity(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderShipmentItem.objects.create(
                    shipment=self.shipment,
                    order_item=self.order_item,
                    product_name=self.order_item.product_name,
                    unit_price=self.order_item.unit_price,
                    quantity=0,
                    total_price=self.order_item.total_price,
                    currency_snapshot=self.order_item.currency_snapshot,
                )

        self.assertFalse(self.shipment.items.exists())

    # Одну позицию заказа нельзя дважды включить
    # в одну и ту же отгрузку.
    def test_shipment_cannot_repeat_same_order_item(self):
        OrderShipmentItem.objects.create(
            shipment=self.shipment,
            order_item=self.order_item,
            product_name=self.order_item.product_name,
            unit_price=self.order_item.unit_price,
            quantity=self.order_item.quantity,
            total_price=self.order_item.total_price,
            currency_snapshot=self.order_item.currency_snapshot,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderShipmentItem.objects.create(
                    shipment=self.shipment,
                    order_item=self.order_item,
                    product_name=self.order_item.product_name,
                    unit_price=self.order_item.unit_price,
                    quantity=self.order_item.quantity,
                    total_price=self.order_item.total_price,
                    currency_snapshot=self.order_item.currency_snapshot,
                )

        self.assertEqual(self.shipment.items.count(), 1)
