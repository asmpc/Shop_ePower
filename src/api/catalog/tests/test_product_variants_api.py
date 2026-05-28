from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from shop_epower.catalog.models import ProductVariantGroup

from .helpers import (
    create_test_brand,
    create_test_category,
    create_test_product,
)


class TestProductVariantsAPI(APITestCase):

    # Проверяем, что detail endpoint товара
    # возвращает связанные варианты товара
    # и передаёт variant_type из группы вариантов.
    def test_product_detail_returns_variants(self):
        brand = create_test_brand(
            name="Variant brand",
            slug="variant-brand",
        )

        category = create_test_category(
            name="Variant category",
            slug="variant-category",
        )

        product1 = create_test_product(
            name="Variant Test White",
            slug="variant-test-white",
            base_price=100,
            brand=brand,
            category=category,
            manufacturer_article="VAR-001-WH",
        )

        product2 = create_test_product(
            name="Variant Test Black",
            slug="variant-test-black",
            base_price=100,
            brand=brand,
            category=category,
            manufacturer_article="VAR-001-BL",
        )

        group = ProductVariantGroup.objects.create(
            name="Variant Test Group",
            variant_type="color",
        )

        group.products.set([product1, product2])

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product1.slug},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("variants", response.data)

        self.assertEqual(
            len(response.data["variants"]),
            1,
        )

        variant = response.data["variants"][0]

        self.assertEqual(
            variant["slug"],
            product2.slug,
        )

        self.assertEqual(
            variant["variant_type"],
            "color",
        )