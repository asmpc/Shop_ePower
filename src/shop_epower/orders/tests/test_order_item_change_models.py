from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.orders.models import (
    OrderItem,
    OrderItemChange,
    OrderItemChangeType,
    OrderStatus,
    OrderStockReservation,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)


class TestsOrderItemChangeModel(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.product = create_test_product(
            base_price=Decimal("100.00"),
        )

        self.order = create_test_order(
            user=self.user,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("500.00"),
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=5,
            total_price=Decimal("500.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

        supplier = create_test_supplier()

        supplier_product = create_test_supplier_product(
            supplier=supplier,
            product=self.product,
            stock_quantity=5,
        )

        OrderStockReservation.objects.create(
            order_item=self.order_item,
            supplier_product=supplier_product,
            quantity=5,
        )

        self.reservations_before = [
            {
                "supplier_product_id": supplier_product.pk,
                "supplier_name": supplier.name,
                "is_own": supplier.is_own,
                "quantity": 7,
            },
        ]

        self.reservations_after = [
            {
                **self.reservations_before[0],
                "quantity": 5,
            },
        ]

    # Проверяем сохранность истории после удаления позиции:
    # запись остаётся у заказа и сохраняет исходный номер,
    # данные изменения, сотрудника, причину и время.
    def test_history_survives_order_item_deletion(self):
        original_item_id = self.order_item.pk
        reason = "Customer requested fewer items."

        change = OrderItemChange.objects.create(
            order=self.order,
            order_item_id_snapshot=original_item_id,
            change_type=OrderItemChangeType.REDUCED,
            product_name=self.order_item.product_name,
            unit_price=self.order_item.unit_price,
            old_quantity=7,
            new_quantity=5,
            old_order_total=Decimal("700.00"),
            new_order_total=Decimal("500.00"),
            currency_snapshot=self.order.currency_snapshot,
            changed_by=self.manager,
            reason=reason,
            reservations_before=self.reservations_before,
            reservations_after=self.reservations_after,
        )

        self.order_item.delete()
        change.refresh_from_db()

        self.assertFalse(self.order.items.exists())
        self.assertEqual(self.order.item_changes.get(), change)
        self.assertEqual(
            change.order_item_id_snapshot,
            original_item_id,
        )
        self.assertEqual(change.product_name, self.product.name)
        self.assertEqual(change.unit_price, Decimal("100.00"))
        self.assertEqual(change.old_quantity, 7)
        self.assertEqual(change.new_quantity, 5)
        self.assertEqual(change.old_order_total, Decimal("700.00"))
        self.assertEqual(change.new_order_total, Decimal("500.00"))
        self.assertEqual(
            change.currency_snapshot,
            self.order.currency_snapshot,
        )
        self.assertEqual(change.changed_by, self.manager)
        self.assertEqual(change.reason, reason)
        self.assertIsNotNone(change.created_at)
        self.assertFalse(
            OrderStockReservation.objects.filter(
                order_item_id=original_item_id,
            ).exists()
        )
        self.assertEqual(
            change.reservations_before,
            self.reservations_before,
        )
        self.assertEqual(
            change.reservations_after,
            self.reservations_after,
        )
