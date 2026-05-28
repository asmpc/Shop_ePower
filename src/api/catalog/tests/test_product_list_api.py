from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .helpers import (
    create_test_brand,
    create_test_category,
    create_test_product,
    assert_inventory_structure,
)


from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .helpers import (
    create_test_brand,
    create_test_category,
    create_test_product,
    assert_inventory_structure,
)


class TestProductListAPI(APITestCase):

    # Проверяем, что API списка товаров
    # возвращает созданный активный товар.
    def test_product_list_returns_products(self):
        create_test_product(
            name="Test product",
            slug="test-product",
        )

        response = self.client.get(
            reverse("api-product-list")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "test-product")

    # Проверяем, что list endpoint возвращает
    # рассчитанную цену final_price и публичный inventory.
    def test_product_list_returns_product_price_and_inventory(self):
        create_test_product(
            name="Test product",
            slug="test-product",
            base_price=100,
        )

        response = self.client.get(
            reverse("api-product-list")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        product_data = response.data[0]

        self.assertEqual(product_data["slug"], "test-product")
        self.assertIn("final_price", product_data)
        self.assertIn("inventory", product_data)
        self.assertEqual(product_data["final_price"], "100.00")

        assert_inventory_structure(
            self,
            product_data["inventory"],
        )

    # Проверяем фильтрацию списка товаров
    # по slug бренда.
    def test_product_list_can_filter_by_brand(self):
        brand_1 = create_test_brand(
            name="Brand 1",
            slug="brand-1",
        )

        brand_2 = create_test_brand(
            name="Brand 2",
            slug="brand-2",
        )

        category = create_test_category()

        create_test_product(
            name="Product 1",
            slug="product-1",
            brand=brand_1,
            category=category,
        )

        create_test_product(
            name="Product 2",
            slug="product-2",
            brand=brand_2,
            category=category,
            manufacturer_article="ART-002",
        )

        response = self.client.get(
            reverse("api-product-list"),
            {"brand": "brand-1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "product-1")

    # Проверяем фильтрацию списка товаров
    # по slug категории.
    def test_product_list_can_filter_by_category(self):
        brand = create_test_brand()

        category_1 = create_test_category(
            name="Category 1",
            slug="category-1",
        )

        category_2 = create_test_category(
            name="Category 2",
            slug="category-2",
        )

        create_test_product(
            name="Product 1",
            slug="product-1",
            brand=brand,
            category=category_1,
            manufacturer_article="ART-001",
        )

        create_test_product(
            name="Product 2",
            slug="product-2",
            brand=brand,
            category=category_2,
            manufacturer_article="ART-002",
        )

        response = self.client.get(
            reverse("api-product-list"),
            {"category": "category-1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "product-1")

    # Проверяем, что фильтр по родительской категории
    # включает товары из дочерних категорий.
    def test_product_list_filter_by_parent_category_includes_child_products(self):
        brand = create_test_brand()

        parent_category = create_test_category(
            name="Cable",
            slug="cable",
        )

        child_category = create_test_category(
            name="Power cable",
            slug="power-cable",
            parent=parent_category,
        )

        create_test_product(
            name="Power Cable Product",
            slug="power-cable-product",
            brand=brand,
            category=child_category,
            manufacturer_article="CABLE-001",
        )

        response = self.client.get(
            reverse("api-product-list"),
            {"category": "cable"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "power-cable-product")