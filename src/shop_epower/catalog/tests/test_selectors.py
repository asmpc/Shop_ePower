from django.test import TestCase

from shop_epower.catalog.models import (
    Brand,
    Category,
    Product,
)

from shop_epower.catalog.selectors.products import (
    get_product_list_queryset,
)


class TestsProductSelectors(TestCase):

    # Проверяем, что фильтрация товаров по родительской категории
    # также включает товары из дочерних категорий.
    # Пример: фильтр по "Cable" должен найти товар из "Power cable".
    def test_product_list_queryset_filter_by_parent_category_includes_child_products(self):
        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        parent_category = Category.objects.create(
            name="Cable",
            slug="cable",
        )

        child_category = Category.objects.create(
            name="Power cable",
            slug="power-cable",
            parent=parent_category,
        )

        Product.objects.create(
            name="Power Cable Product",
            slug="power-cable-product",
            brand=brand,
            category=child_category,
            manufacturer_article="CABLE-001",
            base_price=100,
        )

        queryset = get_product_list_queryset(
            {
                "category": "cable",
            }
        )

        self.assertEqual(
            queryset.count(),
            1,
        )

        self.assertEqual(
            queryset.first().slug,
            "power-cable-product",
        )