from decimal import Decimal

from django.test import TestCase

from shop_epower.orders.models import OrderStatus
from shop_epower.orders.services import (
    create_order_from_cart,
    cancel_new_order,
)
from shop_epower.orders.tests.helpers import (
    create_test_user,
    create_test_product,
    create_test_supplier,
    create_test_supplier_product,
    create_test_cart_with_item,
)


class TestsOrderCancellationServices(TestCase):
    # Проверяем отмену нового заказа:
    # если заказ находится в статусе NEW, клиент может его отменить,
    # статус меняется на CANCELLED, а зарезервированный stock
    # возвращается обратно поставщику.
    def test_cancel_new_order_returns_reserved_stock(self):
        user = create_test_user(
            email="cancel@example.com",
            username="cancel",
            phone="+10000000008",
        )

        product = create_test_product(
            name="Cancel Product",
            brand_name="Cancel Brand",
            category_name="Cancel Category",
            manufacturer_article="CANCEL-001",
            base_price=Decimal("40.00"),
        )

        supplier = create_test_supplier(
            name="Cancel Supplier",
        )

        supplier_product = create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="CANCEL-SUP-001",
            stock_quantity=10,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=3,
            price_snapshot=Decimal("40.00"),
        )
        order = create_order_from_cart(
            user=user,
            cart=cart,
        )

        supplier_product.refresh_from_db()

        self.assertEqual(supplier_product.stock_quantity, 7)
        self.assertEqual(order.status, OrderStatus.NEW)

        cancelled_order = cancel_new_order(
            order=order,
            user=user,
        )

        supplier_product.refresh_from_db()
        cancelled_order.refresh_from_db()

        self.assertEqual(cancelled_order.status, OrderStatus.CANCELLED)
        self.assertEqual(supplier_product.stock_quantity, 10)