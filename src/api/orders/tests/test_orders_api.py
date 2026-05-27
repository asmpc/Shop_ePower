from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient

from shop_epower.cart.models import Cart, CartItem
from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.models import Supplier, SupplierProduct
from shop_epower.orders.models import Order, OrderStatus


User = get_user_model()


class TestsOrdersAPI(TestCase):

    def setUp(self):
        self.client = APIClient()

    # Вспомогательный helper для создания полноценного заказа через API.
    # Создаёт: - бренд - категорию - продукт - поставщика - supplier stock - корзину - checkout
    # Возвращает: - созданный order - supplier_product (для проверки stock)
    def create_order_for_user(self, user, email_prefix="order"):
        brand = Brand.objects.create(
            name=f"{email_prefix} Brand",
        )

        category = Category.objects.create(
            name=f"{email_prefix} Category",
        )

        product = Product.objects.create(
            name=f"{email_prefix} Product",
            brand=brand,
            category=category,
            manufacturer_article=f"{email_prefix.upper()}-001",
            base_price=Decimal("25.00"),
        )

        supplier = Supplier.objects.create(
            name=f"{email_prefix} Supplier",
            is_own=True,
            is_active=True,
        )

        supplier_product = SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article=f"{email_prefix.upper()}-SUP-001",
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
            price_snapshot=Decimal("25.00"),
        )

        response = self.client.post(
            "/api/orders/checkout/",
            {},
            format="json",
        )

        order = Order.objects.get(
            id=response.data["order_id"],
        )

        return order, supplier_product

    # Проверяем список заказов API:
    # пользователь видит только свои заказы,
    # чужие заказы в выдачу не попадают.
    def test_orders_list_api_returns_only_user_orders(self):
        user = User.objects.create_user(
            email="list@example.com",
            username="list",
            password="testpass123",
        )

        other_user = User.objects.create_user(
            email="other-list@example.com",
            username="other-list",
            password="testpass123",
        )

        self.client.force_authenticate(user=user)
        user_order, _ = self.create_order_for_user(
            user=user,
            email_prefix="list",
        )

        self.client.force_authenticate(user=other_user)
        self.create_order_for_user(
            user=other_user,
            email_prefix="otherlist",
        )

        self.client.force_authenticate(user=user)

        response = self.client.get(
            "/api/orders/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], user_order.id)

    # Проверяем detail API заказа:
    # пользователь может получить только свой заказ,
    # а данные заказа и items корректно сериализуются.
    def test_order_detail_api_returns_user_order(self):
        user = User.objects.create_user(
            email="detail@example.com",
            username="detail",
            password="testpass123",
        )

        self.client.force_authenticate(user=user)

        order, _ = self.create_order_for_user(
            user=user,
            email_prefix="detail",
        )

        response = self.client.get(
            f"/api/orders/{order.id}/",
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["id"],
            order.id,
        )

        self.assertEqual(
            len(response.data["items"]),
            1,
        )

        self.assertEqual(
            response.data["items"][0]["product_name"],
            "detail Product",
        )

    # Проверяем защиту detail API:
    # пользователь не может получить чужой заказ.
    def test_order_detail_api_blocks_foreign_order(self):
        owner = User.objects.create_user(
            email="owner@example.com",
            username="owner",
            password="testpass123",
        )

        stranger = User.objects.create_user(
            email="stranger@example.com",
            username="stranger",
            password="testpass123",
        )

        self.client.force_authenticate(user=owner)

        order, _ = self.create_order_for_user(
            user=owner,
            email_prefix="foreign",
        )

        self.client.force_authenticate(user=stranger)

        response = self.client.get(
            f"/api/orders/{order.id}/",
        )

        self.assertEqual(response.status_code, 404)

    # Проверяем cancel API:
    # пользователь может отменить свой NEW заказ,
    # статус меняется на CANCELLED,
    # а stock возвращается обратно поставщику.
    def test_cancel_order_api_restores_stock(self):
        user = User.objects.create_user(
            email="cancel-api@example.com",
            username="cancel-api",
            password="testpass123",
        )

        self.client.force_authenticate(user=user)

        order, supplier_product = self.create_order_for_user(
            user=user,
            email_prefix="cancelapi",
        )

        supplier_product.refresh_from_db()

        # После checkout stock должен уменьшиться:
        # 10 -> 8
        self.assertEqual(
            supplier_product.stock_quantity,
            8,
        )

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        supplier_product.refresh_from_db()

        self.assertEqual(
            order.status,
            OrderStatus.CANCELLED,
        )

        # После отмены stock должен восстановиться:
        # 8 -> 10
        self.assertEqual(
            supplier_product.stock_quantity,
            10,
        )

    # Проверяем ограничения cancel API:
    # заказ не может быть отменён,
    # если его статус уже не NEW.
    def test_cancel_order_api_rejects_non_new_status(self):
        user = User.objects.create_user(
            email="processing@example.com",
            username="processing",
            password="testpass123",
        )

        self.client.force_authenticate(user=user)

        order, _ = self.create_order_for_user(
            user=user,
            email_prefix="processing",
        )

        order.status = OrderStatus.PROCESSING
        order.save(update_fields=["status"])

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            OrderStatus.PROCESSING,
        )

    # Проверяем защиту cancel API:
    # пользователь не может отменить чужой заказ.
    def test_cancel_order_api_blocks_foreign_order(self):
        owner = User.objects.create_user(
            email="owner-cancel@example.com",
            username="owner-cancel",
            password="testpass123",
        )

        stranger = User.objects.create_user(
            email="stranger-cancel@example.com",
            username="stranger-cancel",
            password="testpass123",
        )

        self.client.force_authenticate(user=owner)

        order, _ = self.create_order_for_user(
            user=owner,
            email_prefix="foreigncancel",
        )

        self.client.force_authenticate(user=stranger)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 404)