from django.test import TestCase

from shop_epower.catalog.models import Product, Brand, Category
from shop_epower.suppliers.models import Supplier, SupplierProduct
from shop_epower.suppliers.services.stock import (
    get_product_inventory_data,
)


class TestStockService(TestCase):

    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand")
        self.category = Category.objects.create(name="Test Category")

    def create_product(self):
        return Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            base_price=100,
        )

    # --- TESTS ---

    def test_product_without_suppliers(self):
        product = self.create_product()

        data = get_product_inventory_data(product)

        self.assertEqual(data["total_stock"], 0)
        self.assertFalse(data["in_stock"])
        self.assertEqual(data["supplier_count"], 0)
        self.assertIsNone(data["min_lead_time"])

    def test_single_supplier_stock(self):
        product = self.create_product()

        supplier = Supplier.objects.create(name="Supplier A")

        SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="A1",
            stock_quantity=10,
            lead_time_days=3,
        )

        data = get_product_inventory_data(product)

        self.assertEqual(data["total_stock"], 10)
        self.assertTrue(data["in_stock"])
        self.assertEqual(data["supplier_count"], 1)
        self.assertEqual(data["min_lead_time"], 3)

    def test_multiple_suppliers_aggregation(self):
        product = self.create_product()

        supplier1 = Supplier.objects.create(name="Supplier A")
        supplier2 = Supplier.objects.create(name="Supplier B")

        SupplierProduct.objects.create(
            supplier=supplier1,
            product=product,
            supplier_article="A1",
            stock_quantity=5,
            lead_time_days=5,
        )

        SupplierProduct.objects.create(
            supplier=supplier2,
            product=product,
            supplier_article="B1",
            stock_quantity=7,
            lead_time_days=2,
        )

        data = get_product_inventory_data(product)

        self.assertEqual(data["total_stock"], 12)
        self.assertEqual(data["supplier_count"], 2)
        self.assertEqual(data["min_lead_time"], 2)

    def test_inactive_supplier_not_counted(self):
        product = self.create_product()

        supplier = Supplier.objects.create(
            name="Supplier A",
            is_active=False,
        )

        SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="A1",
            stock_quantity=10,
            lead_time_days=3,
        )

        data = get_product_inventory_data(product)

        self.assertEqual(data["total_stock"], 0)
        self.assertEqual(data["supplier_count"], 0)