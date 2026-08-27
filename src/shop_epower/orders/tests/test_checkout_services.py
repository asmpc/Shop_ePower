from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.cart.tests.helpers import (
    create_test_cart_with_item,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.orders.models import Order
from shop_epower.orders.services import (
    create_order_from_cart,
)
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)

User = get_user_model()


class TestsOrderServices(TestCase):

    # Проверяем checkout service для физлица:
    # заказ создаётся из корзины, данные пользователя копируются,
    # создаётся OrderItem, total_price считается по CartItem,
    # а корзина после checkout становится неактивной.
    def test_create_order_from_cart_for_client(self):
        user = create_test_user(
            email="checkout@example.com",
            username="checkout",
            phone="+10000000004",
        )

        product = create_test_product(
            name="Checkout Product",
            brand_name="Checkout Brand",
            category_name="Checkout Category",
            manufacturer_article="CHECKOUT-001",
            base_price=Decimal("15.00"),
        )

        supplier = create_test_supplier()

        supplier_product = create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-CHECKOUT-001",
            stock_quantity=10,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=2,
            price_snapshot=Decimal("15.00"),
        )

        order = create_order_from_cart(
            user=user,
            cart=cart,
        )

        cart.refresh_from_db()

        supplier_product.refresh_from_db()

        self.assertEqual(order.user, user)
        self.assertFalse(order.is_legal_entity)
        self.assertEqual(order.customer_email, "checkout@example.com")
        self.assertEqual(order.customer_phone, "+10000000004")
        # Проверяем, что по умолчанию используется самовывоз:
        # delivery_address пустой, потому что доставка не выбрана.
        self.assertEqual(order.delivery_address, "")
        self.assertEqual(order.total_price, Decimal("30.00"))

        self.assertEqual(order.items.count(), 1)

        order_item = order.items.first()

        self.assertEqual(order_item.product, product)
        self.assertEqual(order_item.product_name, "Checkout Product")
        self.assertEqual(order_item.unit_price, Decimal("15.00"))
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order_item.total_price, Decimal("30.00"))

        self.assertFalse(cart.is_active)

        self.assertEqual(supplier_product.stock_quantity, 8)

        # Проверяем защиту от oversell:
        # если товара на складе меньше, чем в корзине,
        # checkout должен завершиться ошибкой.
        # Заказ не создаётся, корзина остаётся активной,
        # stock у поставщика не изменяется.
    def test_checkout_raises_error_when_not_enough_stock(self):
        user = create_test_user(
            email="nostock@example.com",
            username="nostock",
            phone="+10000000005",
        )

        product = create_test_product(
            name="No Stock Product",
            brand_name="No Stock Brand",
            category_name="No Stock Category",
            manufacturer_article="NO-STOCK-001",
            base_price=Decimal("20.00"),
        )

        supplier = create_test_supplier(
            name="Own Warehouse No Stock",
        )

        supplier_product = create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-NO-STOCK-001",
            stock_quantity=1,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=2,
            price_snapshot=Decimal("20.00"),
        )

        with self.assertRaises(ValidationError):
            create_order_from_cart(
                user=user,
                cart=cart,
            )

        cart.refresh_from_db()
        supplier_product.refresh_from_db()

        self.assertTrue(cart.is_active)
        self.assertEqual(supplier_product.stock_quantity, 1)
        self.assertEqual(Order.objects.filter(user=user).count(), 0)

    # Проверяем delivery snapshot:
    # checkout service сохраняет delivery данные
    # в Order при создании заказа.
    def test_create_order_from_cart_saves_delivery_data(self):
        user = create_test_user(
            email="delivery@example.com",
            username="delivery",
            phone="+10000000009",
        )

        product = create_test_product(
            name="Delivery Product",
            brand_name="Delivery Brand",
            category_name="Delivery Category",
            manufacturer_article="DELIVERY-001",
            base_price=Decimal("50.00"),
        )

        supplier = create_test_supplier(
            name="Delivery Supplier",
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-DELIVERY-001",
            stock_quantity=10,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=2,
            price_snapshot=Decimal("50.00"),
        )

        order = create_order_from_cart(
            user=user,
            cart=cart,
            delivery_method="shipping",
            delivery_provider="post",
            delivery_address="Test address",
            delivery_comment="Call before delivery",
        )

        cart.refresh_from_db()

        self.assertEqual(order.delivery_method, "shipping")
        self.assertEqual(order.delivery_provider, "post")
        self.assertEqual(order.delivery_address, "Test address")
        self.assertEqual(order.delivery_comment, "Call before delivery")

    # Проверяем, что пользователь с неполным профилем
    # не может создать заказ через service layer.
    def test_create_order_from_cart_requires_complete_profile(self):

        user = create_test_user(
            email="incomplete@example.com",
            username="incomplete",
            first_name="",
        )

        product = create_test_product(
            name="Incomplete Profile Product",
            brand_name="Incomplete Profile Brand",
            category_name="Incomplete Profile Category",
            manufacturer_article="INCOMPLETE-PROFILE-001",
            base_price=Decimal("25.00"),
        )

        supplier = create_test_supplier(
            name="Incomplete Profile Supplier",
        )

        supplier_product = create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-INCOMPLETE-PROFILE-001",
            stock_quantity=10,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=1,
            price_snapshot=Decimal("25.00"),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Complete your profile before placing an order.",
        ):
            create_order_from_cart(
                user=user,
                cart=cart,
            )

        cart.refresh_from_db()
        supplier_product.refresh_from_db()

        self.assertTrue(
            cart.is_active,
        )

        self.assertEqual(
            supplier_product.stock_quantity,
            10,
        )

        self.assertEqual(
            Order.objects.filter(user=user).count(),
            0,
        )

    # Проверяем, что после успешного создания заказа
    # Celery-задачи уведомлений запускаются после commit.
    @patch(
        "shop_epower.orders.services."
        "notify_managers_about_new_order.delay"
    )
    @patch(
        "shop_epower.orders.services."
        "send_customer_order_created_email.delay"
    )
    def test_create_order_schedules_notification_tasks_after_commit(
            self,
            mocked_customer_email_delay,
            mocked_manager_notification_delay,
    ):
        user = create_test_user(
            email="notifications@example.com",
            username="notifications",
            phone="+10000000020",
        )

        product = create_test_product(
            name="Notification Product",
            brand_name="Notification Brand",
            category_name="Notification Category",
            manufacturer_article="NOTIFICATION-001",
            base_price=Decimal("30.00"),
        )

        supplier = create_test_supplier(
            name="Notification Supplier",
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-NOTIFICATION-001",
            stock_quantity=10,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=1,
            price_snapshot=Decimal("30.00"),
        )

        with self.captureOnCommitCallbacks(
                execute=True,
        ):
            order = create_order_from_cart(
                user=user,
                cart=cart,
            )

        mocked_customer_email_delay.assert_called_once_with(
            order.id,
        )

        mocked_manager_notification_delay.assert_called_once_with(
            order.id,
        )

    # Проверяем, что при ошибке создания заказа
    # Celery-задачи уведомлений не запускаются.
    @patch(
        "shop_epower.orders.services."
        "notify_managers_about_new_order.delay"
    )
    @patch(
        "shop_epower.orders.services."
        "send_customer_order_created_email.delay"
    )
    def test_failed_checkout_does_not_schedule_notification_tasks(
            self,
            mocked_customer_email_delay,
            mocked_manager_notification_delay,
    ):
        user = create_test_user(
            email="failed-notifications@example.com",
            username="failed-notifications",
            phone="+10000000021",
        )

        product = create_test_product(
            name="Failed Notification Product",
            brand_name="Failed Notification Brand",
            category_name="Failed Notification Category",
            manufacturer_article="FAILED-NOTIFICATION-001",
            base_price=Decimal("40.00"),
        )

        supplier = create_test_supplier(
            name="Failed Notification Supplier",
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-FAILED-NOTIFICATION-001",
            stock_quantity=1,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=2,
            price_snapshot=Decimal("40.00"),
        )

        with self.captureOnCommitCallbacks(
                execute=True,
        ) as callbacks:
            with self.assertRaises(ValidationError):
                create_order_from_cart(
                    user=user,
                    cart=cart,
                )

        self.assertEqual(
            callbacks,
            [],
        )

        mocked_customer_email_delay.assert_not_called()

        mocked_manager_notification_delay.assert_not_called()