from decimal import Decimal

from django.test import TestCase

from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.models import CategoryMarkup, GlobalMarkup
from shop_epower.suppliers.services.markup import get_markup_percent_for_product


class CategoryMarkupInheritanceTestCase(TestCase):
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

    def test_uses_global_markup_when_no_category_markup(self):
        GlobalMarkup.objects.create(percent=Decimal("20.00"))

        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("20.00"))

    def test_parent_markup_applies_to_child_categories(self):
        GlobalMarkup.objects.create(percent=Decimal("20.00"))

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=True,
        )

        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("30.00"))

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

    def test_inactive_category_markup_is_ignored(self):
        GlobalMarkup.objects.create(percent=Decimal("20.00"))

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=False,
        )

        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("20.00"))

    def test_no_markup_returns_zero(self):
        percent = get_markup_percent_for_product(self.product)

        self.assertEqual(percent, Decimal("0"))