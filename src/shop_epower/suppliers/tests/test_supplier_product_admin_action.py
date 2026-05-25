import uuid
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from shop_epower.suppliers.admin.supplier_product import SupplierProductAdmin
from shop_epower.catalog.models import Product, Brand, Category
from shop_epower.suppliers.models import Supplier, SupplierProduct, GlobalMarkup
from shop_epower.suppliers.services.pricing import recalc_product_base_price
from django.contrib.messages.storage.fallback import FallbackStorage


class TestSupplierProductAdminAction(TestCase):

    # Подготавливаем окружение для тестирования admin action:
    # - создаём fake AdminSite и RequestFactory
    # - создаём товары, поставщика и глобальную наценку
    # - создаём SupplierProduct для двух товаров
    # - создаём экземпляр SupplierProductAdmin
    # Это нужно, чтобы вызвать admin action напрямую, без реального admin UI.
    def setUp(self):
        # Fake admin site и request factory нужны,
        # чтобы протестировать admin action как обычный Python-метод.
        self.site = AdminSite()
        self.factory = RequestFactory()

        # Базовые объекты, необходимые для SupplierProduct
        # и пересчёта цен товаров.
        self.brand = Brand.objects.create(name="Test Brand")
        self.category = Category.objects.create(name="Test Category")
        self.markup = GlobalMarkup.objects.create(percent=20)
        self.supplier = Supplier.objects.create(name="Supplier A", is_own=True)

        # Создаём два продукта с уникальными manufacturer_article,
        # чтобы не нарушить unique constraint товара.
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

        # Создаём позиции поставщика.
        # Именно эти объекты будут передаваться в admin action через queryset.
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

        # Создаём экземпляр ModelAdmin,
        # чтобы вызвать его action напрямую в тесте.
        self.admin = SupplierProductAdmin(SupplierProduct, self.site)

    # Проверяем, что admin action пересчитывает base_price
    # для выбранных SupplierProduct.
    # Проверяем, что admin action пересчитывает base_price
    # для уникальных продуктов из queryset SupplierProduct.
    def test_admin_action_recalculates_base_price(self):
        request = self.factory.get("/")
        setattr(request, "session", {})
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        queryset = SupplierProduct.objects.filter(
            id__in=[self.sp1.id, self.sp2.id]
        )

        self.admin.recalc_base_price_action(
            request,
            queryset,
        )

        self.product1.refresh_from_db()
        self.product2.refresh_from_db()

        # 100 + 20% = 120
        self.assertEqual(self.product1.base_price, 120)

        # 150 + 20% = 180
        self.assertEqual(self.product2.base_price, 180)