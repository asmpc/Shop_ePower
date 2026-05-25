from django.test import TestCase
from shop_epower.catalog.models import Product, Brand, Category
from shop_epower.suppliers.models import Supplier, SupplierProduct, GlobalMarkup
from shop_epower.suppliers.services.pricing import recalc_product_base_price


class TestSupplierProductPricing(TestCase):
    # Подготавливаем базовые объекты для тестов пересчёта base_price:
    # продукт, собственного поставщика, внешнего поставщика
    # и глобальную наценку 20%.
    def setUp(self):
        # Создаем базовые объекты
        self.brand = Brand.objects.create(name="Test Brand")
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            base_price=0,
        )
        self.supplier_own = Supplier.objects.create(name="Our Warehouse", is_own=True)
        self.supplier_ext = Supplier.objects.create(name="External Supplier", is_own=False)
        self.markup = GlobalMarkup.objects.create(percent=20)

    # Проверяем пересчёт base_price при одном поставщике.
    # Берётся supplier_price и применяется GlobalMarkup:
    # 100 + 20% = 120.
    def test_single_supplier_price(self):
        # Один поставщик
        sp = SupplierProduct.objects.create(
            supplier=self.supplier_own,
            product=self.product,
            supplier_article="A1",
            supplier_price=100,
            stock_quantity=10
        )

        recalc_product_base_price(self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.base_price, 120)  # 100 + 20%

    # Проверяем пересчёт base_price при нескольких поставщиках.
    # Сервис должен взять максимальную закупочную цену
    # и применить к ней GlobalMarkup:
    # 110 + 20% = 132.
    def test_multiple_suppliers_max_price(self):
        # Несколько поставщиков, берется max цена
        SupplierProduct.objects.create(
            supplier=self.supplier_own,
            product=self.product,
            supplier_article="A1",
            supplier_price=100,
            stock_quantity=10
        )
        SupplierProduct.objects.create(
            supplier=self.supplier_ext,
            product=self.product,
            supplier_article="B1",
            supplier_price=110,
            stock_quantity=5
        )

        recalc_product_base_price(self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.base_price, 132)  # 110 + 20%

    # Проверяем, что неактивный поставщик не участвует в расчёте base_price.
    # Даже если у него supplier_price выше, он должен быть проигнорирован.
    def test_inactive_supplier_ignored(self):
        # Неактивный поставщик не учитывается
        inactive_supplier = Supplier.objects.create(name="Inactive Supplier", is_own=False, is_active=False)
        SupplierProduct.objects.create(
            supplier=inactive_supplier,
            product=self.product,
            supplier_article="X1",
            supplier_price=200,
            stock_quantity=5
        )

        # Активный поставщик с меньшей ценой
        SupplierProduct.objects.create(
            supplier=self.supplier_own,
            product=self.product,
            supplier_article="A1",
            supplier_price=100,
            stock_quantity=10
        )

        recalc_product_base_price(self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.base_price, 120)  # 100 + 20%, не учитывается 200 неактивного

    # Проверяем, что после изменения supplier_price
    # повторный пересчёт обновляет product.base_price.
    # Это важно для админки и обновления цен поставщиков.
    def test_supplier_product_update_triggers_recalc(self):
        # Проверяем, что после изменения supplier_price пересчет работает
        sp = SupplierProduct.objects.create(
            supplier=self.supplier_own,
            product=self.product,
            supplier_article="A1",
            supplier_price=100,
            stock_quantity=10
        )

        # Меняем цену
        sp.supplier_price = 150
        sp.save()

        recalc_product_base_price(self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.base_price, 180)  # 150 + 20%