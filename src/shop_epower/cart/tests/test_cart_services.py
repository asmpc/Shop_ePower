from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.cart.models import CartItem

from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.services.stock import get_product_inventory_public
from unittest.mock import patch
from shop_epower.cart.services import (
    add_product_to_cart,
    clear_cart,
    get_or_create_cart,
)



class TestCartServices(TestCase):

    def setUp(self):
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

    def test_add_product_to_cart_rejects_zero_quantity(self):
        with self.assertRaises(ValidationError):
            add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=0,
            )

    def test_add_product_to_cart_rejects_negative_quantity(self):
        with self.assertRaises(ValidationError):
            add_product_to_cart(
                cart=self.cart,
                product=self.product,
                quantity=-1,
            )

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