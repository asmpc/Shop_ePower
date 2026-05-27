from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory

from shop_epower.cart.models import CartItem, Cart

from shop_epower.catalog.models import Brand, Category, Product

from unittest.mock import patch
from shop_epower.cart.services import (
    add_product_to_cart,
    clear_cart,
    get_or_create_cart,
    merge_session_cart_to_user_cart,
)

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import get_user_model


class TestsCartServices(TestCase):

    def setUp(self):

        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        self.category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        self.product = Product.objects.create(
            name="Test product",
            slug="test-product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="ART-001",
            base_price=Decimal("10.00"),
        )

        self.cart = get_or_create_cart(
            session_key="test-session",
        )

    # Проверяем, что для неавторизованного пользователя создаётся активная корзина,
    # привязанная к session_key.
    def test_get_or_create_cart_creates_cart_for_session(self):
        cart = get_or_create_cart(
            session_key="another-session",
        )

        self.assertEqual(
            cart.session_key,
            "another-session",
        )

        self.assertTrue(
            cart.is_active,
        )

    # Проверяем, что товар добавляется в корзину как новый CartItem.
    # Stock мокается, чтобы тестировать только cart service, а не suppliers.
    def test_add_product_to_cart_creates_item(self):
        with patch(
                "shop_epower.cart.services.get_product_inventory_public",
                return_value={
                    "own_stock": 10,
                    "supplier_stock": 0,
                    "total_available": 10,
                    "min_lead_time": None,
                    "in_stock": True,
                },
        ):
            item = add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=2,
            )

        self.assertEqual(CartItem.objects.count(), 1)
        self.assertEqual(item.quantity, 2)

    # Проверяем, что при добавлении товара фиксируется price_snapshot.
    # Это важно: цена в корзине должна храниться отдельно от текущей цены товара.
    def test_add_product_to_cart_stores_price_snapshot(self):
        with patch(
                "shop_epower.cart.services.get_product_inventory_public",
                return_value={
                    "own_stock": 10,
                    "supplier_stock": 0,
                    "total_available": 10,
                    "min_lead_time": None,
                    "in_stock": True,
                },
        ):
            item = add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=1,
            )

            self.assertEqual(
                item.price_snapshot,
                Decimal("10.00"),
            )

    # Проверяем, что повторное добавление того же товара не создаёт новый CartItem,
    # а увеличивает quantity у уже существующей позиции.
    def test_add_product_to_cart_increases_quantity_if_item_exists(self):
        with patch(
                "shop_epower.cart.services.get_product_inventory_public",
                return_value={
                    "own_stock": 10,
                    "supplier_stock": 0,
                    "total_available": 10,
                    "min_lead_time": None,
                    "in_stock": True,
                },
        ):
            add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=2,
            )

            item = add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=3,
            )

            self.assertEqual(
                item.quantity,
                5,
            )

            self.assertEqual(
                CartItem.objects.count(),
                1,
            )

    # Проверяем защиту от некорректного количества: quantity=0 запрещён.
    def test_add_product_to_cart_rejects_zero_quantity(self):
        with self.assertRaises(ValidationError):
            add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=0,
            )

    # Проверяем защиту от отрицательного количества.
    def test_add_product_to_cart_rejects_negative_quantity(self):
        with self.assertRaises(ValidationError):
            add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=-1,
            )

    # Проверяем, что нельзя добавить в корзину больше товара,
    # чем доступно на складе и у поставщиков.
    def test_add_product_to_cart_rejects_quantity_above_available_stock(self):
        with patch(
                "shop_epower.cart.services.get_product_inventory_public",
                return_value={
                    "own_stock": 1,
                    "supplier_stock": 0,
                    "total_available": 1,
                    "min_lead_time": None,
                    "in_stock": True,
                },
        ):
            with self.assertRaises(ValidationError):
                add_product_to_cart(
                    cart=self.cart,
                    product=self.product,
                    quantity=2,
                )

    # Проверяем, что clear_cart удаляет все позиции из корзины,
    # но сам объект Cart при этом остаётся.
    def test_clear_cart_removes_all_items(self):
        with patch(
            "shop_epower.cart.services.get_product_inventory_public",
            return_value={
                "own_stock": 10,
                "supplier_stock": 0,
                "total_available": 10,
                "min_lead_time": None,
                "in_stock": True,
            },
        ):
            add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=2,
            )

        self.assertEqual(
            CartItem.objects.count(),
            1,
        )

        clear_cart(self.cart)

        self.assertEqual(
            CartItem.objects.count(),
            0,
        )

    # Проверяем merge guest cart -> user cart после логина.
    # Гостевая корзина находится по старому session_key и переносится в корзину пользователя.
    def test_merge_session_cart_to_user_cart_moves_guest_items_to_user_cart(self):
        request = RequestFactory().get("/")
        request.session = SessionStore()
        request.session.save()

        guest_cart = get_or_create_cart(
            session_key=request.session.session_key,
        )

        CartItem.objects.create(
            cart=guest_cart,
            product=self.product,
            quantity=2,
            price_snapshot=Decimal("100.00"),
            currency_snapshot="BYN",
        )

        cart_updated = merge_session_cart_to_user_cart(
            request=request,
            user=self.user,
            old_session_key=request.session.session_key,
        )

        self.assertTrue(cart_updated)

        user_cart = Cart.objects.get(user=self.user, is_active=True)

        self.assertTrue(
            CartItem.objects.filter(
                cart=user_cart,
                product=self.product,
                quantity=2,
            ).exists()
        )

        self.assertFalse(
            Cart.objects.filter(id=guest_cart.id).exists()
        )

    # Проверяем, что если такой товар уже есть в user cart,
    # то при merge quantity складывается, а дубль CartItem не создаётся.
    def test_merge_session_cart_to_existing_user_cart_merges_quantity(self):
        request = RequestFactory().get("/")
        request.session = SessionStore()
        request.session.save()

        guest_cart = get_or_create_cart(
            session_key=request.session.session_key,
        )

        CartItem.objects.create(
            cart=guest_cart,
            product=self.product,
            quantity=2,
            price_snapshot=Decimal("100.00"),
            currency_snapshot="BYN",
        )

        user_cart = get_or_create_cart(user=self.user)

        CartItem.objects.create(
            cart=user_cart,
            product=self.product,
            quantity=3,
            price_snapshot=Decimal("90.00"),
            currency_snapshot="BYN",
        )

        cart_updated = merge_session_cart_to_user_cart(
            request=request,
            user=self.user,
            old_session_key=request.session.session_key,
        )

        self.assertTrue(cart_updated)

        item = CartItem.objects.get(
            cart=user_cart,
            product=self.product,
        )

        self.assertEqual(item.quantity, 5)

    # Проверяем безопасное поведение: если guest cart не найдена,
    # service ничего не меняет и возвращает False.
    def test_merge_session_cart_to_user_cart_returns_false_without_guest_cart(self):
        request = RequestFactory().get("/")
        request.session = SessionStore()
        request.session.save()

        cart_updated = merge_session_cart_to_user_cart(
            request=request,
            user=self.user,
            old_session_key=request.session.session_key,
        )

        self.assertFalse(cart_updated)

    # Проверяем, что при merge цена пересчитывается под авторизованного пользователя,
    # а не переносится старый guest price_snapshot.
    def test_merge_session_cart_recalculates_price_for_user(self):
        request = RequestFactory().get("/")
        request.session = SessionStore()
        request.session.save()

        guest_cart = get_or_create_cart(
            session_key=request.session.session_key,
        )

        CartItem.objects.create(
            cart=guest_cart,
            product=self.product,
            quantity=1,
            price_snapshot=Decimal("999.00"),
            currency_snapshot="BYN",
        )

        expected_price = self.product.get_price_for_user(self.user)

        merge_session_cart_to_user_cart(
            request=request,
            user=self.user,
            old_session_key=request.session.session_key,
        )

        user_cart = Cart.objects.get(user=self.user, is_active=True)

        item = CartItem.objects.get(
            cart=user_cart,
            product=self.product,
        )

        self.assertEqual(item.price_snapshot, expected_price)

