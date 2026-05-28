from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.exceptions import ValidationError

from shop_epower.orders.services import update_order_status_by_manager, update_order_delivery_by_manager
from shop_epower.suppliers.models import Supplier, SupplierProduct
from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.cart.models import Cart, CartItem
from shop_epower.orders.services import create_order_from_cart
from shop_epower.orders.models import Order, OrderStatus, OrderItem


User = get_user_model()



class TestsManagerOrderWorkflow(TestCase):

    # Проверяем manager workflow:
    # пользователь с ролью manager может перевести заказ
    # из статуса NEW в статус PROCESSING.
    def test_manager_can_move_order_from_new_to_processing(self):
        manager = User.objects.create_user(
            email="manager@example.com",
            username="manager",
            password="testpass123",
            role="manager",
        )

        client = User.objects.create_user(
            email="client-status@example.com",
            username="client-status",
            password="testpass123",
        )

        order = Order.objects.create(
            user=client,
            status=OrderStatus.NEW,
            is_legal_entity=False,
            customer_name="Client Status",
            customer_email="client-status@example.com",
            customer_phone="+10000000009",
            total_price=Decimal("100.00"),
        )

        updated_order = update_order_status_by_manager(
            order=order,
            user=manager,
            new_status=OrderStatus.PROCESSING,
        )

        updated_order.refresh_from_db()

        self.assertEqual(
            updated_order.status,
            OrderStatus.PROCESSING,
        )

    # Проверяем следующий шаг manager workflow:
    # пользователь с ролью manager может перевести заказ
    # из статуса PROCESSING в статус COMPLETED.
    def test_manager_can_move_order_from_processing_to_completed(self):
        manager = User.objects.create_user(
            email="manager-complete@example.com",
            username="manager-complete",
            password="testpass123",
            role="manager",
        )

        client = User.objects.create_user(
            email="client-complete@example.com",
            username="client-complete",
            password="testpass123",
        )

        order = Order.objects.create(
            user=client,
            status=OrderStatus.PROCESSING,
            is_legal_entity=False,
            customer_name="Client Complete",
            customer_email="client-complete@example.com",
            customer_phone="+10000000010",
            total_price=Decimal("150.00"),
        )

        updated_order = update_order_status_by_manager(
            order=order,
            user=manager,
            new_status=OrderStatus.COMPLETED,
        )

        updated_order.refresh_from_db()

        self.assertEqual(
            updated_order.status,
            OrderStatus.COMPLETED,
        )

    # Проверяем permissions manager workflow:
    # обычный клиент не может изменять статус заказа.
    def test_client_cannot_update_order_status(self):
        client_user = User.objects.create_user(
            email="simple-client@example.com",
            username="simple-client",
            password="testpass123",
            role="client",
        )

        order_owner = User.objects.create_user(
            email="order-owner@example.com",
            username="order-owner",
            password="testpass123",
        )

        order = Order.objects.create(
            user=order_owner,
            status=OrderStatus.NEW,
            is_legal_entity=False,
            customer_name="Order Owner",
            customer_email="order-owner@example.com",
            customer_phone="+10000000011",
            total_price=Decimal("200.00"),
        )

        with self.assertRaises(ValidationError):
            update_order_status_by_manager(
                order=order,
                user=client_user,
                new_status=OrderStatus.PROCESSING,
            )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            OrderStatus.NEW,
        )

    # Проверяем ограничения manager workflow:
    # заказ нельзя перевести напрямую
    # из статуса NEW в статус COMPLETED.
    def test_invalid_order_status_transition(self):
        manager = User.objects.create_user(
            email="invalid-transition@example.com",
            username="invalid-transition",
            password="testpass123",
            role="manager",
        )

        client = User.objects.create_user(
            email="transition-client@example.com",
            username="transition-client",
            password="testpass123",
        )

        order = Order.objects.create(
            user=client,
            status=OrderStatus.NEW,
            is_legal_entity=False,
            customer_name="Transition Client",
            customer_email="transition-client@example.com",
            customer_phone="+10000000012",
            total_price=Decimal("300.00"),
        )

        with self.assertRaises(ValidationError):
            update_order_status_by_manager(
                order=order,
                user=manager,
                new_status=OrderStatus.COMPLETED,
            )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            OrderStatus.NEW,
        )

    # Проверяем manager cancellation workflow:
    # менеджер может отменить заказ в статусе PROCESSING,
    # статус меняется на CANCELLED,
    # а зарезервированный stock возвращается поставщику.
    def test_manager_can_cancel_processing_order_and_restore_stock(self):
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

        supplier_product.refresh_from_db()
        self.assertEqual(supplier_product.stock_quantity, 7)

        updated_order = update_order_status_by_manager(
            order=order,
            user=manager,
            new_status=OrderStatus.CANCELLED,
            cancellation_reason="supplier_unavailable",
            cancellation_comment="Supplier did not ship the order.",
        )

        supplier_product.refresh_from_db()
        updated_order.refresh_from_db()

        self.assertEqual(updated_order.status, OrderStatus.CANCELLED)
        self.assertEqual(supplier_product.stock_quantity, 10)
        self.assertEqual(
            updated_order.cancellation_reason,
            "supplier_unavailable",
        )

        self.assertEqual(
            updated_order.cancellation_comment,
            "Supplier did not ship the order.",
        )