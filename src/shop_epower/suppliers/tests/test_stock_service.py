from django.test import TestCase

from shop_epower.catalog.models import Product, Brand, Category
from shop_epower.suppliers.models import Supplier, SupplierProduct
from shop_epower.suppliers.services.stock import (
    get_product_inventory_data,
)
from shop_epower.suppliers.services.stock import get_product_inventory_public



class TestStockService(TestCase):

    # Подготавливаем общие Brand и Category.
    # Они нужны для создания Product в каждом тесте stock service.
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand")
        self.category = Category.objects.create(name="Test Category")

    # Helper для создания тестового продукта.
    # Используется, чтобы не дублировать создание Product в каждом тесте.
    def create_product(self):
        return Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            base_price=100,
        )

    # Проверяем товар без поставщиков:
    # stock равен 0, товара нет в наличии,
    # поставщиков нет, минимальный срок поставки отсутствует.
    def test_product_without_suppliers(self):
        product = self.create_product()

        data = get_product_inventory_data(product)

        self.assertEqual(data["total_stock"], 0)
        self.assertFalse(data["in_stock"])
        self.assertEqual(data["supplier_count"], 0)
        self.assertIsNone(data["min_lead_time"])

    # Проверяем агрегацию склада для одного активного поставщика:
    # total_stock равен stock_quantity поставщика,
    # supplier_count равен 1,
    # min_lead_time берётся из SupplierProduct.
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

    # Проверяем агрегацию по нескольким поставщикам:
    # total_stock суммируется,
    # supplier_count считает активных поставщиков,
    # min_lead_time выбирается минимальный.
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

    # Проверяем, что неактивный поставщик не участвует в расчётах:
    # его stock_quantity и наличие не должны попадать в inventory data.
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


class TestPublicInventoryService(TestCase):

    # Подготавливаем продукт, собственного поставщика-склад
    # и внешнего поставщика.
    # Это нужно, чтобы отдельно проверять own_stock и supplier_stock.
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand")
        self.category = Category.objects.create(name="Test Category")

        self.product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="PUBLIC-INV-001",
            base_price=100,
        )

        self.own_supplier = Supplier.objects.create(
            name="Own Warehouse",
            is_own=True,
            is_active=True,
        )

        self.external_supplier = Supplier.objects.create(
            name="External Supplier",
            is_own=False,
            is_active=True,
        )

    # Проверяем публичный inventory для товара без остатков:
    # собственный склад = 0, поставщики = 0,
    # total_available = 0, товар не в наличии.
    def test_public_inventory_without_stock(self):
        data = get_product_inventory_public(self.product)

        self.assertEqual(data["own_stock"], 0)
        self.assertEqual(data["supplier_stock"], 0)
        self.assertEqual(data["total_available"], 0)
        self.assertIsNone(data["min_lead_time"])
        self.assertFalse(data["in_stock"])

    # Проверяем публичный inventory, когда товар есть только на своём складе.
    # own_stock учитывается сразу, supplier_stock остаётся 0,
    # min_lead_time отсутствует, потому что ждать поставщика не нужно.
    def test_public_inventory_with_own_stock_only(self):
        SupplierProduct.objects.create(
            supplier=self.own_supplier,
            product=self.product,
            supplier_article="OWN-001",
            supplier_price=50,
            currency="BYN",
            stock_quantity=10,
            lead_time_days=0,
        )

        data = get_product_inventory_public(self.product)

        self.assertEqual(data["own_stock"], 10)
        self.assertEqual(data["supplier_stock"], 0)
        self.assertEqual(data["total_available"], 10)
        self.assertIsNone(data["min_lead_time"])
        self.assertTrue(data["in_stock"])

    # Проверяем публичный inventory, когда товар есть только у внешнего поставщика.
    # Такой товар доступен под заказ: supplier_stock > 0,
    # min_lead_time показывает срок поставки.
    def test_public_inventory_with_supplier_stock_only(self):
        SupplierProduct.objects.create(
            supplier=self.external_supplier,
            product=self.product,
            supplier_article="EXT-001",
            supplier_price=50,
            currency="BYN",
            stock_quantity=35,
            lead_time_days=5,
        )

        data = get_product_inventory_public(self.product)

        self.assertEqual(data["own_stock"], 0)
        self.assertEqual(data["supplier_stock"], 35)
        self.assertEqual(data["total_available"], 35)
        self.assertEqual(data["min_lead_time"], 5)
        self.assertTrue(data["in_stock"])

    # Проверяем публичный inventory, когда товар есть и на своём складе,
    # и у внешнего поставщика.
    # total_available должен быть суммой own_stock + supplier_stock.
    def test_public_inventory_with_own_and_supplier_stock(self):
        SupplierProduct.objects.create(
            supplier=self.own_supplier,
            product=self.product,
            supplier_article="OWN-001",
            supplier_price=50,
            currency="BYN",
            stock_quantity=10,
            lead_time_days=0,
        )

        SupplierProduct.objects.create(
            supplier=self.external_supplier,
            product=self.product,
            supplier_article="EXT-001",
            supplier_price=50,
            currency="BYN",
            stock_quantity=35,
            lead_time_days=5,
        )

        data = get_product_inventory_public(self.product)

        self.assertEqual(data["own_stock"], 10)
        self.assertEqual(data["supplier_stock"], 35)
        self.assertEqual(data["total_available"], 45)
        self.assertEqual(data["min_lead_time"], 5)
        self.assertTrue(data["in_stock"])

    # Проверяем, что внешний неактивный поставщик игнорируется
    # в публичном inventory и не увеличивает доступное количество.
    def test_public_inventory_ignores_inactive_supplier(self):
        inactive_supplier = Supplier.objects.create(
            name="Inactive Supplier",
            is_own=False,
            is_active=False,
        )

        SupplierProduct.objects.create(
            supplier=inactive_supplier,
            product=self.product,
            supplier_article="INACTIVE-001",
            supplier_price=50,
            currency="BYN",
            stock_quantity=99,
            lead_time_days=2,
        )

        data = get_product_inventory_public(self.product)

        self.assertEqual(data["supplier_stock"], 0)
        self.assertEqual(data["total_available"], 0)
        self.assertFalse(data["in_stock"])

    # Проверяем, что среди нескольких внешних поставщиков
    # min_lead_time выбирается как минимальный срок поставки.
    def test_public_inventory_uses_min_supplier_lead_time(self):
        SupplierProduct.objects.create(
            supplier=self.external_supplier,
            product=self.product,
            supplier_article="EXT-001",
            supplier_price=50,
            currency="BYN",
            stock_quantity=10,
            lead_time_days=7,
        )

        second_supplier = Supplier.objects.create(
            name="Fast Supplier",
            is_own=False,
            is_active=True,
        )

        SupplierProduct.objects.create(
            supplier=second_supplier,
            product=self.product,
            supplier_article="EXT-002",
            supplier_price=60,
            currency="BYN",
            stock_quantity=20,
            lead_time_days=3,
        )

        data = get_product_inventory_public(self.product)

        self.assertEqual(data["supplier_stock"], 30)
        self.assertEqual(data["min_lead_time"], 3)

    # Проверяем, что неактивный SupplierProduct не учитывается,
    # даже если сам поставщик активен.
    def test_public_inventory_ignores_inactive_supplier_product(self):
        SupplierProduct.objects.create(
            supplier=self.external_supplier,
            product=self.product,
            supplier_article="EXT-001",
            supplier_price=50,
            currency="BYN",
            stock_quantity=25,
            lead_time_days=5,
            is_active=False,
        )

        data = get_product_inventory_public(self.product)

        self.assertEqual(data["supplier_stock"], 0)
        self.assertEqual(data["total_available"], 0)
        self.assertFalse(data["in_stock"])