from django.test import TestCase
from decimal import Decimal

from shop_epower.catalog.models import Product
from shop_epower.accounts.models import User, PriceCategory
from shop_epower.catalog.models import Brand, Category


class TestPricingCase(TestCase):

    def setUp(self):
        self.category_discount = PriceCategory.objects.create(
            name="Installer",
            discount_percent=10
        )

        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="123456",
            price_category=self.category_discount
        )

        # 🔥 FIX: обязательные связи
        self.brand = Brand.objects.create(
            name="Test Brand",
            slug="test-brand"
        )

        self.category = Category.objects.create(
            name="Test Category",
            slug="test-category"
        )

        self.product = Product.objects.create(
            name="Test Product",
            manufacturer_article="ART-1",
            base_price=Decimal("100.00"),
            brand=self.brand,
            category=self.category,
        )

    def test_anonymous_user_price(self):

        price = self.product.get_price_for_user(None)

        self.assertEqual(price, Decimal("100.00"))

    def test_user_with_discount(self):

        price = self.product.get_price_for_user(self.user)

        self.assertEqual(price, Decimal("90.00"))

    def test_user_without_category(self):

        self.user.price_category = None
        self.user.save()

        price = self.product.get_price_for_user(self.user)

        self.assertEqual(price, Decimal("100.00"))