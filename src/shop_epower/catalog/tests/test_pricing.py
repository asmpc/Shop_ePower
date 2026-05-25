from django.test import TestCase
from decimal import Decimal

from shop_epower.catalog.models import Product
from shop_epower.accounts.models import User, PriceCategory
from shop_epower.catalog.models import Brand, Category

#Цена товара зависит от пользователя и его price_category, иначе — base_price
class TestPricing(TestCase):

    # Подготавливаем данные для тестов pricing:
    # - создаём категорию цен с процентной скидкой
    # - создаём пользователя с этой категорией
    # - создаём продукт с базовой ценой
    # Важно: brand и category обязательны для Product (иначе модель не сохранится)
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

    # Проверяем, что для анонимного пользователя цена товара равна base_price,
    # т.е. никакие скидки не применяются.
    def test_anonymous_user_price(self):

        price = self.product.get_price_for_user(None)

        self.assertEqual(price, Decimal("100.00"))

    # Проверяем, что для пользователя с ценовой категорией применяется скидка.
    # В данном случае 10% от 100 → итоговая цена должна быть 90.
    def test_user_with_discount(self):

        price = self.product.get_price_for_user(self.user)

        self.assertEqual(price, Decimal("90.00"))

    # Проверяем, что если у пользователя нет price_category,
    # то цена рассчитывается как для обычного пользователя без скидки (base_price).
    def test_user_without_category(self):

        self.user.price_category = None
        self.user.save()

        price = self.product.get_price_for_user(self.user)

        self.assertEqual(price, Decimal("100.00"))