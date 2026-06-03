from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient

from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.models import Supplier, SupplierProduct


User = get_user_model()


class TestsSuppliersAPI(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            email="supplier-api@example.com",
            username="supplier-api",
            password="testpass123",
        )

        self.brand = Brand.objects.create(
            name="Supplier API Brand",
        )

        self.category = Category.objects.create(
            name="Supplier API Category",
        )

        self.product = Product.objects.create(
            name="Supplier API Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="SUPPLIER-API-001",
            base_price="100.00",
        )

        self.supplier = Supplier.objects.create(
            name="Supplier API",
            is_own=False,
            is_active=True,
        )

        self.supplier_product = SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-API-001",
            stock_quantity=10,
            lead_time_days=3,
            is_active=True,
        )

    # Проверяем suppliers list API:
    # авторизованный пользователь может получить список активных поставщиков.
    def test_suppliers_list_api_returns_active_suppliers(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/suppliers/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.supplier.id)
        self.assertEqual(response.data[0]["name"], "Supplier API")

    # Проверяем suppliers API auth:
    # неавторизованный пользователь не может получить список поставщиков.
    def test_suppliers_list_api_requires_authentication(self):
        response = self.client.get(
            "/api/suppliers/",
        )

        self.assertEqual(response.status_code, 401)

    # Проверяем supplier detail API:
    # авторизованный пользователь может получить активного поставщика по id.
    def test_supplier_detail_api_returns_supplier(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/suppliers/{self.supplier.id}/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.supplier.id)
        self.assertEqual(response.data["name"], "Supplier API")

    # Проверяем suppliers API filtering:
    # неактивные поставщики не попадают в список.
    def test_suppliers_list_api_excludes_inactive_suppliers(self):
        Supplier.objects.create(
            name="Inactive Supplier API",
            is_own=False,
            is_active=False,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/suppliers/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.supplier.id)

    # Проверяем supplier products list API:
    # авторизованный пользователь может получить список активных supplier products.
    def test_supplier_products_list_api_returns_active_items(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/supplier-products/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.supplier_product.id)
        self.assertEqual(response.data[0]["supplier_name"], "Supplier API")
        self.assertEqual(response.data[0]["product_name"], "Supplier API Product")

    # Проверяем supplier products API auth:
    # неавторизованный пользователь не может получить supplier products.
    def test_supplier_products_list_api_requires_authentication(self):
        response = self.client.get(
            "/api/supplier-products/",
        )

        self.assertEqual(response.status_code, 401)

    # Проверяем supplier product detail API:
    # авторизованный пользователь может получить supplier product по id.
    def test_supplier_product_detail_api_returns_item(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/supplier-products/{self.supplier_product.id}/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.supplier_product.id)
        self.assertEqual(response.data["supplier_name"], "Supplier API")
        self.assertEqual(response.data["product_name"], "Supplier API Product")

    # Проверяем supplier products API filtering:
    # неактивные supplier products не попадают в список.
    def test_supplier_products_list_api_excludes_inactive_items(self):
        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-API-INACTIVE-001",
            stock_quantity=5,
            lead_time_days=5,
            is_active=False,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/supplier-products/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.supplier_product.id)

    # Проверяем supplier products API filtering:
    # товары неактивных поставщиков не попадают в список.
    def test_supplier_products_list_api_excludes_items_from_inactive_suppliers(self):
        inactive_supplier = Supplier.objects.create(
            name="Inactive Parent Supplier API",
            is_own=False,
            is_active=False,
        )

        SupplierProduct.objects.create(
            supplier=inactive_supplier,
            product=self.product,
            supplier_article="SUP-API-INACTIVE-PARENT-001",
            stock_quantity=5,
            lead_time_days=5,
            is_active=True,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/supplier-products/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.supplier_product.id)