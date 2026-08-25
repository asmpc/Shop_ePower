from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.cart.tests.helpers import create_test_cart_with_item
from shop_epower.catalog.tests.helpers import (
    create_test_brand,
    create_test_category,
    create_test_product,
)
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.services import (
    create_order_from_cart,
    update_order_delivery_by_manager,
)
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)


class TestsManagerDeliveryWorkflow(TestCase):

    def setUp(self):
        self.manager = create_test_manager()
        self.client = create_test_user()

        brand = create_test_brand(
            name="Manager Cancel Brand",
        )

        category = create_test_category(
            name="Manager Cancel Category",
        )

        product = create_test_product(
            name="Manager Cancel Product",
            brand=brand,
            category=category,
            manufacturer_article="MANAGER-CANCEL-001",
            base_price=Decimal("10.00"),
        )

        supplier = create_test_supplier(
            name="Manager Cancel Supplier",
            is_own=True,
            is_active=True,
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="MANAGER-CANCEL-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = create_test_cart_with_item(
            user=self.client,
            product=product,
            quantity=3,
            price_snapshot=Decimal("10.00"),
        )

        self.order = create_order_from_cart(
            user=self.client,
            cart=cart,
        )

        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

    # Проверяем manager delivery pricing:
    # если доставка не оплачивается при получении,
    # delivery cost прибавляется к total_price заказа.
    def test_manager_delivery_cost_is_added_to_order_total(self):

        self.assertEqual(self.order.total_price, Decimal("30.00"))

        updated_order = update_order_delivery_by_manager(
            order=self.order,
            user=self.manager,
            delivery_cost=Decimal("25.00"),
            delivery_paid_by_customer_on_receipt=False,
            delivery_method="shipping",
            manager_delivery_comment="Delivery included in order total.",
        )

        self.assertEqual(
            updated_order.total_price,
            Decimal("55.00"),
        )

    # Проверяем manager delivery pricing:
    # если доставка оплачивается при получении,
    # delivery cost сохраняется, но не прибавляется к total_price.
    def test_manager_delivery_cost_is_not_added_when_paid_on_receipt(self):

        updated_order = update_order_delivery_by_manager(
            order=self.order,
            user=self.manager,
            delivery_cost=Decimal("25.00"),
            delivery_paid_by_customer_on_receipt=True,
            delivery_method="shipping",
            manager_delivery_comment="Customer pays delivery on receipt.",
        )

        self.assertEqual(
            updated_order.delivery_cost,
            Decimal("25.00"),
        )

        self.assertEqual(
            updated_order.total_price,
            Decimal("30.00"),
        )

        self.assertTrue(
            updated_order.delivery_paid_by_customer_on_receipt,
        )

