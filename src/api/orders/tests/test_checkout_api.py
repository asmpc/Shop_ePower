from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient

from shop_epower.cart.models import Cart, CartItem
from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.models import Supplier, SupplierProduct
from shop_epower.orders.models import Order, OrderStatus


User = get_user_model()

class TestsCheckoutAPI(TestCase):

    # Проверяем, что checkout API требует авторизацию:
    # неавторизованный пользователь не может оформить заказ.
    def test_checkout_api_requires_authentication(self):

        client = APIClient()

        response = client.post(
            "/api/orders/checkout/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    # Проверяем, что checkout API создаёт заказ:
    # авторизованный пользователь с активной корзиной и доступным stock
    # получает созданный заказ и статус HTTP 201.
    def test_checkout_api_creates_order(self):

        user = User.objects.create_user(
            email="api@example.com",
            username="api",
            password="testpass123",
            phone="+10000000007",
        )

        client = APIClient()
        client.force_authenticate(user=user)

        brand = Brand.objects.create(
            name="API Brand",
        )

        category = Category.objects.create(
            name="API Category",
        )

        product = Product.objects.create(
            name="API Product",
            brand=brand,
            category=category,
            manufacturer_article="API-001",
            base_price=Decimal("50.00"),
        )

        supplier = Supplier.objects.create(
            name="API Supplier",
            is_own=True,
            is_active=True,
        )

        SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="API-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            price_snapshot=Decimal("50.00"),
        )

        response = client.post(
            "/api/orders/checkout/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("order_id", response.data)
        self.assertEqual(response.data["total_price"], "100.00")

        self.assertEqual(Order.objects.filter(user=user).count(), 1)

    # Проверяем, что checkout API не оформляет пустую корзину:
    # если активная корзина есть, но товаров в ней нет,
    # endpoint возвращает HTTP 400 и заказ не создаётся.
    def test_checkout_api_fails_with_empty_cart(self):

        user = User.objects.create_user(
            email="empty@example.com",
            username="empty",
            password="testpass123",
        )

        client = APIClient()
        client.force_authenticate(user=user)

        Cart.objects.create(
            user=user,
            is_active=True,
        )

        response = client.post(
            "/api/orders/checkout/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.filter(user=user).count(), 0)

    # Проверяем checkout delivery flow:
    # checkout API сохраняет delivery данные
    # в созданном заказе.
    def test_checkout_api_saves_delivery_data(self):
        user = User.objects.create_user(
            email="api@example.com",
            username="api",
            password="testpass123",
            phone="+10000000007",
        )

        client = APIClient()
        client.force_authenticate(user=user)

        brand = Brand.objects.create(
            name="API Brand",
        )

        category = Category.objects.create(
            name="API Category",
        )

        product = Product.objects.create(
            name="API Product",
            brand=brand,
            category=category,
            manufacturer_article="API-001",
            base_price=Decimal("50.00"),
        )

        supplier = Supplier.objects.create(
            name="API Supplier",
            is_own=True,
            is_active=True,
        )

        SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="API-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            price_snapshot=Decimal("50.00"),
        )

        response = client.post(
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
