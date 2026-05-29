from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shop_epower.orders.services import update_order_delivery_by_manager
from shop_epower.suppliers.models import Supplier, SupplierProduct
from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.cart.models import Cart, CartItem
from shop_epower.orders.services import create_order_from_cart
from shop_epower.orders.models import OrderStatus


User = get_user_model()



class TestsManagerDeliveryWorkflow(TestCase):

    # Проверяем manager delivery pricing:
    # если доставка не оплачивается при получении,
    # delivery cost прибавляется к total_price заказа.
    def test_manager_delivery_cost_is_added_to_order_total(self):
        manager = User.objects.create_user(
            email="manager-cancel@example.com",
            username="manager-cancel",
            password="testpass123",
            role="manager",
        )

        client = User.objects.create_user(
            email="client-manager-cancel@example.com",
            username="client-manager-cancel",
            password="testpass123",
            phone="+10000000030",
        )

        brand = Brand.objects.create(name="Manager Cancel Brand")
        category = Category.objects.create(name="Manager Cancel Category")

        product = Product.objects.create(
            name="Manager Cancel Product",
            brand=brand,
            category=category,
            manufacturer_article="MANAGER-CANCEL-001",
            base_price=Decimal("10.00"),
        )

        supplier = Supplier.objects.create(
            name="Manager Cancel Supplier",
            is_own=True,
            is_active=True,
        )

        supplier_product = SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="MANAGER-CANCEL-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(user=client)

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=3,
            price_snapshot=Decimal("10.00"),
        )

        order = create_order_from_cart(
            user=client,
            cart=cart,
        )

        order.status = OrderStatus.PROCESSING
        order.save(update_fields=["status"])

        self.assertEqual(order.total_price, Decimal("30.00"))

        updated_order = update_order_delivery_by_manager(
            order=order,
            user=manager,
            delivery_cost=Decimal("25.00"),
            delivery_paid_by_customer_on_receipt=False,
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
        manager = User.objects.create_user(
            email="manager-cancel@example.com",
            username="manager-cancel",
            password="testpass123",
            role="manager",
        )

        client = User.objects.create_user(
            email="client-manager-cancel@example.com",
            username="client-manager-cancel",
            password="testpass123",
            phone="+10000000030",
        )

        brand = Brand.objects.create(name="Manager Cancel Brand")
        category = Category.objects.create(name="Manager Cancel Category")

        product = Product.objects.create(
            name="Manager Cancel Product",
            brand=brand,
            category=category,
            manufacturer_article="MANAGER-CANCEL-001",
            base_price=Decimal("10.00"),
        )

        supplier = Supplier.objects.create(
            name="Manager Cancel Supplier",
            is_own=True,
            is_active=True,
        )

        supplier_product = SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="MANAGER-CANCEL-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(user=client)

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=3,
            price_snapshot=Decimal("10.00"),
        )

        order = create_order_from_cart(
            user=client,
            cart=cart,
        )

        order.status = OrderStatus.PROCESSING
        order.save(update_fields=["status"])

        updated_order = update_order_delivery_by_manager(
            order=order,
            user=manager,
            delivery_cost=Decimal("25.00"),
            delivery_paid_by_customer_on_receipt=True,
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

