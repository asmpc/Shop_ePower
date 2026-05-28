from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from shop_epower.catalog.models import ProductImage

from .helpers import (
    create_test_product,
    assert_inventory_structure,
)


class TestProductDetailAPI(APITestCase):

    # Проверяем, что detail endpoint товара
    # возвращает основные данные товара,
    # final_price и публичный inventory.
    def test_product_detail_returns_product(self):
        product = create_test_product(
            name="Test product",
            slug="test-product",
            base_price=100,
        )

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data["slug"], "test-product")
        self.assertEqual(response.data["final_price"], "100.00")

        self.assertIn("inventory", response.data)
        self.assertIn("brand", response.data)
        self.assertIn("images", response.data)

        assert_inventory_structure(
            self,
            response.data["inventory"],
        )

    # Проверяем, что detail endpoint
    # возвращает изображения товара
    # и не отдаёт manager-only данные.
    def test_product_detail_returns_images(self):
        product = create_test_product(
            name="Test product",
            slug="test-product",
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data["images"]), 1)

        self.assertEqual(
            response.data["images"][0]["alt_text"],
            "Test image",
        )

        self.assertTrue(
            response.data["images"][0]["is_primary"]
        )

        self.assertNotIn(
            "supplier_inventory_details",
            response.data,
        )

        self.assertNotIn(
            "cost_summary",
            response.data,
        )