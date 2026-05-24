from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from shop_epower.catalog.models import Product, Brand, Category
from django.core.files.uploadedfile import SimpleUploadedFile

from shop_epower.catalog.models import ProductImage
from django.contrib.auth import get_user_model

User = get_user_model()

class TestProductListAPI(APITestCase):

    def test_product_list_returns_products(self):
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
        )

        response = self.client.get(
            reverse("api-product-list")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            response.data[0]["slug"],
            "test-product",
        )

    def test_product_list_returns_product_price_and_inventory(self):
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
            base_price=100,
        )

        response = self.client.get(
            reverse("api-product-list")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[0]["slug"],
            "test-product",
        )

        self.assertIn(
            "final_price",
            response.data[0],
        )

        self.assertIn(
            "inventory",
            response.data[0],
        )

        self.assertEqual(
            response.data[0]["final_price"],
            "100.00",
        )

    def test_product_detail_returns_product(self):
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
            base_price=100,
        )

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product.slug},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["slug"],
            "test-product",
        )

        self.assertEqual(
            response.data["final_price"],
            "100.00",
        )

        self.assertIn(
            "inventory",
            response.data,
        )

        self.assertIn(
            "brand",
            response.data
        )

        self.assertIn(
            "images",
            response.data,
        )

    def test_product_detail_returns_images(self):
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
            base_price=100,
        )

        image = SimpleUploadedFile(
            name="test.jpg",
            content=b"test image content",
            content_type="image/jpeg",
        )

        ProductImage.objects.create(
            product=product,
            image=image,
            alt_text="Test image",
            is_primary=True,
            sort_order=1,
        )

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product.slug},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["images"]),
            1,
        )

        self.assertEqual(
            response.data["images"][0]["alt_text"],
            "Test image",
        )

        self.assertTrue(
            response.data["images"][0]["is_primary"],
        )

        self.assertNotIn(
            "supplier_inventory_details",
            response.data
        )

        self.assertNotIn(
            "cost_summary",
            response.data
        )

    def test_product_detail_returns_manager_data_for_manager(self):
        user = User.objects.create_user(
            email="manager@test.com",
            username="manager",
            password="12345678",
            role="manager",
        )

        self.client.force_authenticate(user=user)

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
            base_price=100,
        )

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("supplier_inventory_details", response.data)
        self.assertIn("cost_summary", response.data)