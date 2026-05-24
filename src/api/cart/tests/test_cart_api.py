from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from decimal import Decimal
from unittest.mock import patch

from shop_epower.catalog.models import Brand, Category, Product



class TestCartAPI(APITestCase):

    def test_cart_detail_returns_empty_cart(self):
        response = self.client.get(
            reverse("api-cart-detail")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["items"],
            [],
        )

        self.assertEqual(
            response.data["total_price"],
            "0.00",
        )

        self.assertEqual(
            response.data["total_quantity"],
            0,
        )

    def test_cart_add_item(self):
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

        with patch(
                "shop_epower.cart.services.get_product_inventory_public",
                return_value={
                    "own_stock": 10,
                    "supplier_stock": 0,
                    "total_available": 10,
                    "min_lead_time": None,
                    "in_stock": True,
                },
        ):
            response = self.client.post(
                reverse("api-cart-add"),
                {
                    "product": str(product.id),
                    "quantity": 2,
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["total_quantity"],
            2,
        )

        self.assertEqual(
            len(response.data["items"]),
            1,
        )

    def test_cart_add_same_product_increases_quantity(self):
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

        with patch(
                "shop_epower.cart.services.get_product_inventory_public",
                return_value={
                    "own_stock": 10,
                    "supplier_stock": 0,
                    "total_available": 10,
                    "min_lead_time": None,
                    "in_stock": True,
                },
        ):
            self.client.post(
                reverse("api-cart-add"),
                {
                    "product": str(product.id),
                    "quantity": 2,
                },
                format="json",
            )

            response = self.client.post(
                reverse("api-cart-add"),
                {
                    "product": str(product.id),
                    "quantity": 3,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total_quantity"], 5)
        self.assertEqual(response.data["items"][0]["quantity"], 5)

    def test_cart_remove_item(self):
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

        with patch(
                "shop_epower.cart.services.get_product_inventory_public",
                return_value={
                    "own_stock": 10,
                    "supplier_stock": 0,
                    "total_available": 10,
                    "min_lead_time": None,
                    "in_stock": True,
                },
        ):
            self.client.post(
                reverse("api-cart-add"),
                {
                    "product": str(product.id),
                    "quantity": 2,
                },
                format="json",
            )

        response = self.client.post(
            reverse("api-cart-remove"),
            {
                "product": str(product.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["total_quantity"],
            0,
        )

        self.assertEqual(
            len(response.data["items"]),
            0,
        )

def test_cart_clear(self):
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

    with patch(
        "shop_epower.cart.services.get_product_inventory_public",
        return_value={
            "own_stock": 10,
            "supplier_stock": 0,
            "total_available": 10,
            "min_lead_time": None,
            "in_stock": True,
        },
    ):
        self.client.post(
            reverse("api-cart-add"),
            {
                "product": str(product.id),
                "quantity": 2,
            },
            format="json",
        )

    response = self.client.post(
        reverse("api-cart-clear"),
        format="json",
    )

    self.assertEqual(
        response.status_code,
        status.HTTP_200_OK,
    )

    self.assertEqual(
        response.data["items"],
        [],
    )

    self.assertEqual(
        response.data["total_price"],
        "0.00",
    )

    self.assertEqual(
        response.data["total_quantity"],
        0,
    )


