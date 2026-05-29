from decimal import Decimal

from django.test import TestCase

from shop_epower.orders.services import create_order_from_cart
from shop_epower.orders.tests.helpers import (
    create_test_user,
    create_test_product,
    create_test_supplier,
    create_test_supplier_product,
    create_test_cart_with_item,
)



class TestsOrderReservationServices(TestCase):
    # Проверяем порядок списания stock:
    # сначала checkout списывает товар с нашего склада (is_own=True),
    # а если там не хватает — добирает остаток у внешнего поставщика.
    def test_checkout_reserves_stock_from_own_supplier_first(self):
        user = create_test_user(
            email="multistock@example.com",
            username="multistock",
            phone="+10000000006",
        )

        product = create_test_product(
            name="Multi Stock Product",
            brand_name="Multi Stock Brand",
            category_name="Multi Stock Category",
            manufacturer_article="MULTI-STOCK-001",
            base_price=Decimal("30.00"),
        )

        own_supplier = create_test_supplier(
            name="Own Warehouse Multi",
            is_own=True,
        )

        external_supplier = create_test_supplier(
            name="External Supplier Multi",
            is_own=False,
        )

        own_supplier_product = create_test_supplier_product(
            supplier=own_supplier,
            product=product,
            supplier_article="OWN-MULTI-001",
            stock_quantity=2,
        )

        external_supplier_product = create_test_supplier_product(
            supplier=external_supplier,
            product=product,
            supplier_article="EXT-MULTI-001",
            stock_quantity=5,
            lead_time_days=3,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=4,
            price_snapshot=Decimal("30.00"),
        )

        order = create_order_from_cart(
            user=user,
            cart=cart,
        )

        own_supplier_product.refresh_from_db()
        external_supplier_product.refresh_from_db()

        self.assertEqual(order.total_price, Decimal("120.00"))

        self.assertEqual(own_supplier_product.stock_quantity, 0)
        self.assertEqual(external_supplier_product.stock_quantity, 3)