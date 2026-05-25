from decimal import Decimal

from django.test import TestCase

from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.models import (
    CategoryMarkup,
    CurrencyRate,
    GlobalMarkup,
    Supplier,
    SupplierProduct,
)
from shop_epower.suppliers.services.currency import CurrencyService


class CategoryMarkupPricingTestCase(TestCase):

    # Подготавливаем продукт с поставщиком и закупочной ценой.
    # Продукт находится в глубокой иерархии категорий:
    # Parent → Child → SubChild.
    # Это нужно, чтобы протестировать:
    # - приоритет category markup
    # - корректный пересчёт base_price
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand")

        self.parent_category = Category.objects.create(name="Parent")
        self.child_category = Category.objects.create(
            name="Child",
            parent=self.parent_category,
        )
        self.subchild_category = Category.objects.create(
            name="SubChild",
            parent=self.child_category,
        )

        self.product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.subchild_category,
            manufacturer_article="MARKUP-PRICE-001",
            base_price=0,
        )

        self.supplier = Supplier.objects.create(
            name="Test Supplier",
            is_active=True,
        )

        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-001",
            supplier_price=Decimal("100.00"),
            currency="BYN",
            stock_quantity=10,
            lead_time_days=3,
            is_active=True,
        )

    # Проверяем базовый сценарий:
    # если для категории товара нет CategoryMarkup,
    # используется глобальная наценка (GlobalMarkup).
    # Цена считается в базовой валюте проекта.
    def test_base_price_uses_global_markup(self):
        GlobalMarkup.objects.create(
            percent=Decimal("20.00"),
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("120.00"))

    # Проверяем, что CategoryMarkup родительской категории
    # применяется к товарам в дочерних категориях
    # и переопределяет GlobalMarkup.
    def test_base_price_uses_parent_category_markup(self):
        GlobalMarkup.objects.create(
            percent=Decimal("20.00"),
        )

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=True,
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("130.00"))

    # Проверяем приоритет ближайшей категории:
    # если есть markup у дочерней категории,
    # он имеет приоритет над родительской и глобальной наценкой.
    def test_base_price_uses_closest_child_category_markup(self):
        GlobalMarkup.objects.create(
            percent=Decimal("20.00"),
        )

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=True,
        )

        CategoryMarkup.objects.create(
            category=self.child_category,
            percent=Decimal("25.00"),
            is_active=True,
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("125.00"))

    # Проверяем, что неактивная CategoryMarkup игнорируется,
    # и логика корректно откатывается к GlobalMarkup.
    def test_inactive_category_markup_falls_back_to_global(self):
        GlobalMarkup.objects.create(
            percent=Decimal("20.00"),
        )

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=False,
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("120.00"))

    # Проверяем полный сценарий:
    # - цена поставщика в другой валюте (например RUB)
    # - конвертация в базовую валюту проекта
    # - применение category markup
    # Важно: расчёт должен быть независим от конкретной валюты (не только BYN).
    def test_base_price_uses_currency_conversion_and_category_markup(self):
        CurrencyRate.objects.create(
            currency="RUB",
            rate_to_base_currency=Decimal("0.038700"),
        )

        self.product.supplier_products.all().delete()

        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-RUB-001",
            supplier_price=Decimal("1000.00"),
            currency="RUB",
            stock_quantity=10,
            lead_time_days=3,
            is_active=True,
        )

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=True,
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("50.31"))

    # Проверяем максимальный приоритет:
    # markup категории самого товара (самая глубокая категория)
    # должен переопределять:
    # - markup родительских категорий
    # - GlobalMarkup
    def test_base_price_uses_product_category_markup_first(self):
        GlobalMarkup.objects.create(
            percent=Decimal("20.00"),
        )

        CategoryMarkup.objects.create(
            category=self.parent_category,
            percent=Decimal("30.00"),
            is_active=True,
        )

        CategoryMarkup.objects.create(
            category=self.child_category,
            percent=Decimal("25.00"),
            is_active=True,
        )

        CategoryMarkup.objects.create(
            category=self.subchild_category,
            percent=Decimal("15.00"),
            is_active=True,
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("115.00"))

    # Проверяем поведение при отсутствии курса валюты:
    # если цена поставщика указана в валюте, для которой нет CurrencyRate,
    # пересчёт base_price должен выбросить ValueError.
    def test_base_price_update_raises_error_when_currency_rate_is_missing(self):
        self.product.supplier_products.all().delete()

        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-USD-001",
            supplier_price=Decimal("100.00"),
            currency="USD",
            stock_quantity=10,
            lead_time_days=3,
            is_active=True,
        )

        with self.assertRaises(ValueError):
            CurrencyService.update_product_base_price(self.product)