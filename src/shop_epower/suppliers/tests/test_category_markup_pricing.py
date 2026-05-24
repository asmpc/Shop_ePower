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

    def test_base_price_uses_global_markup(self):
        GlobalMarkup.objects.create(
            percent=Decimal("20.00"),
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("120.00"))

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

    def test_base_price_uses_currency_conversion_and_category_markup(self):
        CurrencyRate.objects.create(
            currency="RUB",
            rate_to_BYN=Decimal("0.038700"),
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

        # 1000 RUB * 0.0387 = 38.70 BYN
        # 38.70 + 30% = 50.31 BYN
        self.assertEqual(self.product.base_price, Decimal("50.31"))