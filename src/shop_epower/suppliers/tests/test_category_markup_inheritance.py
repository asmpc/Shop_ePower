from decimal import Decimal

from django.test import TestCase

from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.models import CategoryMarkup, GlobalMarkup
from shop_epower.suppliers.services.markup import get_markup_percent_for_product


class CategoryMarkupInheritanceTestCase(TestCase):

    # Подготавливаем дерево категорий:
    # Parent → Child → SubChild.
    # Продукт лежит в самой глубокой категории, чтобы проверить,
    # как наценка ищется вверх по цепочке родителей.
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand")

        # Дерево категорий
        self.parent_category = Category.objects.create(name="Parent")
        self.child_category = Category.objects.create(
            name="Child",
            parent=self.parent_category,
        )
        self.subchild_category = Category.objects.create(
            name="SubChild",
            parent=self.child_category,
        )

        self.product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.subchild_category,
            manufacturer_article="TEST-001",
            base_price=100,
        )

    # Проверяем fallback-логику:
    # если для категории товара и её родителей нет CategoryMarkup,
    # используется глобальная наценка GlobalMarkup.
    def test_uses_global_markup_when_no_category_markup(self):
        GlobalMarkup.objects.create(percent=Decimal("20.00"))

        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("20.00"))

    # Проверяем наследование наценки:
    # если наценка задана у родительской категории,
    # она применяется к товарам из дочерних категорий.
    def test_parent_markup_applies_to_child_categories(self):
        GlobalMarkup.objects.create(percent=Decimal("20.00"))

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=True,
        )

        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("30.00"))

    # Проверяем приоритет более близкой категории:
    # наценка дочерней категории должна переопределять наценку родителя.
    def test_child_markup_overrides_parent(self):
        GlobalMarkup.objects.create(percent=Decimal("20.00"))

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=True,
        )

        CategoryMarkup.objects.create(
            category=self.child_category,
            percent=Decimal("25.00"),
            is_active=True,
        )

        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("25.00"))

    # Проверяем, что неактивная CategoryMarkup игнорируется.
    # В таком случае service должен перейти к fallback — GlobalMarkup.
    def test_inactive_category_markup_is_ignored(self):
        GlobalMarkup.objects.create(percent=Decimal("20.00"))

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=False,
        )

        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("20.00"))

    # Проверяем самый безопасный fallback:
    # если нет ни category markup, ни global markup,
    # service возвращает 0% наценки.
    def test_no_markup_returns_zero(self):
        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("0"))

    # Проверяем, что наценка категории самого продукта
    # имеет наивысший приоритет и переопределяет:
    # - наценку родительских категорий
    # - глобальную наценку
    def test_product_category_markup_has_highest_priority(self):
        GlobalMarkup.objects.create(percent=Decimal("20.00"))

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=True,
        )

        CategoryMarkup.objects.create(
            category=self.child_category,
            percent=Decimal("25.00"),
            is_active=True,
        )

        CategoryMarkup.objects.create(
            category=self.subchild_category,
            percent=Decimal("15.00"),
            is_active=True,
        )

        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("15.00"))