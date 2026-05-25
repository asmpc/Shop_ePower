from decimal import Decimal

from django.test import TestCase

from shop_epower.cart.models import Cart, CartItem
from shop_epower.catalog.models import Brand, Category, Product


class TestCartModels(TestCase):

    # Проверяем, что property total_price у CartItem корректно рассчитывает
    # итоговую стоимость как price_snapshot * quantity.
    # Это важно, потому что в корзине используется зафиксированная цена (snapshot),
    # а не текущая цена товара.
    def test_cart_item_total_price(self):
        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        product = Product.objects.create(
            name="Test product",
            slug="test-product",
            brand=brand,
            category=category,
            manufacturer_article="ART-001",
            base_price=Decimal("10.00"),
        )

        cart = Cart.objects.create(
            session_key="test-session",
        )

        item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=3,
            price_snapshot=Decimal("10.00"),
            currency_snapshot="BYN",
        )

        self.assertEqual(
            item.total_price,
            Decimal("30.00"),
        )