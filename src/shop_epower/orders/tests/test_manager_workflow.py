from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.cart.tests.helpers import (
    create_test_cart_with_item,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.orders.models import Order, OrderItem, OrderStatus
from shop_epower.orders.services import (
    create_order_from_cart,
    update_order_delivery_by_manager,
    update_order_status_by_manager,
)
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)


class TestsManagerOrderWorkflow(TestCase):

    def setUp(self):
        self.manager = create_test_manager()
        self.client = create_test_user()

    # Проверяем manager workflow:
    # пользователь с ролью manager может перевести заказ
    # из статуса NEW в статус PROCESSING.
    def test_manager_can_move_order_from_new_to_processing(self):

        order = Order.objects.create(
            user=self.client,
            status=OrderStatus.NEW,
            is_legal_entity=False,
            customer_name="Client Status",
            customer_email="client-status@example.com",
            customer_phone="+10000000009",
            total_price=Decimal("100.00"),
        )

        updated_order = update_order_status_by_manager(
            order=order,
            user=self.manager,
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

        order = Order.objects.create(
            user=self.client,
            status=OrderStatus.PROCESSING,
            is_legal_entity=False,
            customer_name="Client Complete",
            customer_email="client-complete@example.com",
            customer_phone="+10000000010",
            total_price=Decimal("150.00"),
        )

        updated_order = update_order_status_by_manager(
            order=order,
            user=self.manager,
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
        client_user = create_test_user(
            email="simple-client@example.com",
            username="simple-client",
            password="testpass123",
            phone="+10000000030",
            first_name="John",
            last_name="Doe",
        )

        order_owner = create_test_user(
            email="order-owner@example.com",
            username="order-owner",
            password="testpass123",
            phone="+10000000030",
            first_name="John",
            last_name="Doe",
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

        order = Order.objects.create(
            user=self.client,
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
                user=self.manager,
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
        product = create_test_product(
            name="Manager Cancel Product",
            brand_name="Manager Cancel Brand",
            category_name="Manager Cancel Category",
            manufacturer_article="MANAGER-CANCEL-001",
            base_price=Decimal("10.00"),
        )

        supplier = create_test_supplier(
            name="Manager Cancel Supplier",
            is_own=True,
            is_active=True,
        )

        supplier_product = create_test_supplier_product(
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

        order = create_order_from_cart(
            user=self.client,
            cart=cart,
        )

        order.status = OrderStatus.PROCESSING
        order.save(update_fields=["status"])

        supplier_product.refresh_from_db()
        self.assertEqual(supplier_product.stock_quantity, 7)

        updated_order = update_order_status_by_manager(
            order=order,
            user=self.manager,
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