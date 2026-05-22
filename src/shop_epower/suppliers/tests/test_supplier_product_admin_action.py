import uuid
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from shop_epower.suppliers.admin.supplier_product import SupplierProductAdmin
from shop_epower.catalog.models import Product, Brand, Category
from shop_epower.suppliers.models import Supplier, SupplierProduct, GlobalMarkup
from shop_epower.suppliers.services.pricing import recalc_product_base_price


class TestSupplierProductAdminAction(TestCase):
    def setUp(self):
        # Admin site
        self.site = AdminSite()
        self.factory = RequestFactory()

        # Создаем объекты
        self.brand = Brand.objects.create(name="Test Brand")
        self.category = Category.objects.create(name="Test Category")
        self.markup = GlobalMarkup.objects.create(percent=20)
        self.supplier = Supplier.objects.create(name="Supplier A", is_own=True)

        # Создаем продукты с уникальными manufacturer_article
        self.product1 = Product.objects.create(
            name="Product 1",
            brand=self.brand,
            category=self.category,
            base_price=0,
            manufacturer_article=str(uuid.uuid4())  # уникальное значение
        )
        self.product2 = Product.objects.create(
            name="Product 2",
            brand=self.brand,
            category=self.category,
            base_price=0,
            manufacturer_article=str(uuid.uuid4())  # уникальное значение
        )

        # Создаем SupplierProduct
        self.sp1 = SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product1,
            supplier_article="A1",
            supplier_price=100,
            stock_quantity=5
        )
        self.sp2 = SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product2,
            supplier_article="A2",
            supplier_price=150,
            stock_quantity=3
        )

        # Admin instance
        self.admin = SupplierProductAdmin(SupplierProduct, self.site)