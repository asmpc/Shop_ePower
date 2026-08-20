from decimal import Decimal

from django.test import TestCase

from rest_framework.test import APIClient

from shop_epower.cart.models import Cart, CartItem
from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.orders.models import Order
from shop_epower.accounts.tests.helpers import create_test_user

from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)



class TestsCheckoutAPI(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="api@example.com",
            username="test_api",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            phone="+10000000007",
        )

        self.brand = Brand.objects.create(
            name="API Brand",
        )

        self.category = Category.objects.create(
            name="API Category",
        )

        self.client = APIClient()

    # Проверяем, что checkout API требует авторизацию:
    # неавторизованный пользователь не может оформить заказ.
    def test_checkout_api_requires_authentication(self):

        # client = APIClient()

        response = self.client.post(
            "/api/orders/checkout/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    # Проверяем, что checkout API создаёт заказ:
    # авторизованный пользователь с активной корзиной и доступным stock
    # получает созданный заказ и статус HTTP 201.
    def test_checkout_api_creates_order(self):

        self.client.force_authenticate(user=self.user)

        product = Product.objects.create(
            name="API Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="API-001",
            base_price=Decimal("50.00"),
        )

        supplier = create_test_supplier(
            name="API Supplier",
            is_own=True,
            is_active=True,
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="API-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=self.user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            price_snapshot=Decimal("50.00"),
        )

        response = self.client.post(
            "/api/orders/checkout/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("order_id", response.data)
        self.assertEqual(response.data["total_price"], "100.00")

        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)

    # Проверяем, что checkout API не оформляет пустую корзину:
    # если активная корзина есть, но товаров в ней нет,
    # endpoint возвращает HTTP 400 и заказ не создаётся.
    def test_checkout_api_fails_with_empty_cart(self):

        self.client.force_authenticate(user=self.user)

        Cart.objects.create(
            user=self.user,
            is_active=True,
        )

        response = self.client.post(
            "/api/orders/checkout/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 0)

    # Проверяем checkout delivery flow:
    # checkout API сохраняет delivery данные
    # в созданном заказе.
    def test_checkout_api_saves_delivery_data(self):

        self.client.force_authenticate(user=self.user)

        product = Product.objects.create(
            name="API Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="API-001",
            base_price=Decimal("50.00"),
        )

        supplier = create_test_supplier(
            name="API Supplier",
            is_own=True,
            is_active=True,
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="API-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=self.user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            price_snapshot=Decimal("50.00"),
        )

        response = self.client.post(
            "/api/orders/checkout/",
            {
                "delivery_method": "shipping",
                "delivery_provider": "post",
                "delivery_address": "API address",
                "delivery_comment": "API comment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        order = Order.objects.get(
            id=response.data["order_id"],
        )

        self.assertEqual(order.delivery_method, "shipping")
        self.assertEqual(order.delivery_provider, "post")
        self.assertEqual(order.delivery_address, "API address")
        self.assertEqual(order.delivery_comment, "API comment")

    # Проверяем, что checkout API
    # не позволяет оформить заказ
    # с неполным профилем.
    def test_checkout_api_requires_complete_profile(self):

        self.user.first_name = ""
        self.user.save(
            update_fields=["first_name"],
        )

        self.client.force_authenticate(
            user=self.user,
        )

        product = Product.objects.create(
            name="API Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="API-001",
            base_price=Decimal("50.00"),
        )

        supplier = create_test_supplier(
            name="API Supplier",
            is_own=True,
            is_active=True,
        )

        supplier_product = create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="API-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=self.user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            price_snapshot=Decimal("50.00"),
        )

        response = self.client.post(
            "/api/orders/checkout/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

        supplier_product.refresh_from_db()

        self.assertEqual(
            supplier_product.stock_quantity,
            10,
        )

        cart.refresh_from_db()

        self.assertTrue(
            cart.is_active,
        )

        self.assertEqual(
            response.data["detail"],
            [
                "Complete your profile before placing an order."
            ],
        )
