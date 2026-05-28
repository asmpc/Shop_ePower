from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .helpers import create_test_product

User = get_user_model()


class TestProductPermissionsAPI(APITestCase):

    # Проверяем, что обычный client
    # не получает manager-only данные товара.
    def test_product_detail_does_not_return_manager_data_for_client(self):
        user = User.objects.create_user(
            email="client@test.com",
            username="client",
            password="12345678",
            role="client",
        )

        self.client.force_authenticate(user=user)

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

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertNotIn(
            "supplier_inventory_details",
            response.data,
        )

        self.assertNotIn(
            "cost_summary",
            response.data,
        )

    # Проверяем, что manager получает
    # расширенные supplier данные товара.
    def test_product_detail_returns_manager_data_for_manager(self):
        user = User.objects.create_user(
            email="manager@test.com",
            username="manager",
            password="12345678",
            role="manager",
        )

        self.client.force_authenticate(user=user)

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

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "supplier_inventory_details",
            response.data,
        )

        self.assertIn(
            "cost_summary",
            response.data,
        )