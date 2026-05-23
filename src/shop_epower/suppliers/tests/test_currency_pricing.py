from decimal import Decimal

from django.test import TestCase

from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.models import (
    CurrencyRate,
    GlobalMarkup,
    Supplier,
    SupplierProduct,
)
from shop_epower.suppliers.services.currency import CurrencyService


class TestCurrencyPricing(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand")
        self.category = Category.objects.create(name="Test Category")

        self.product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="TEST-001",
            base_price=0,
        )

        self.supplier = Supplier.objects.create(
            name="Test Supplier",
            is_active=True,
        )

        GlobalMarkup.objects.create(
            percent=20,
        )

    def test_convert_rub_to_byn(self):
        CurrencyRate.objects.create(
            currency="RUB",
            rate_to_BYN=Decimal("0.038700"),
        )

        result = CurrencyService.convert(
            amount=Decimal("1000"),
            from_currency="RUB",
            to_currency="BYN",
        )

        self.assertEqual(result, Decimal("38.70"))

    def test_convert_byn_to_rub(self):
        CurrencyRate.objects.create(
            currency="RUB",
            rate_to_BYN=Decimal("0.038700"),
        )

        result = CurrencyService.convert(
            amount=Decimal("288"),
            from_currency="BYN",
            to_currency="RUB",
        )

        self.assertEqual(result, Decimal("7441.86"))

    def test_recalculate_base_price_from_byn_supplier_price(self):
        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-BYN-001",
            supplier_price=Decimal("100"),
            currency="BYN",
            stock_quantity=10,
            lead_time_days=0,
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("120.00"))

    def test_recalculate_base_price_from_rub_supplier_price(self):
        CurrencyRate.objects.create(
            currency="RUB",
            rate_to_BYN=Decimal("0.038700"),
        )

        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-RUB-001",
            supplier_price=Decimal("1000"),
            currency="RUB",
            stock_quantity=10,
            lead_time_days=3,
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        # 1000 RUB * 0.0387 = 38.70 BYN
        # 38.70 + 20% = 46.44 BYN
        self.assertEqual(self.product.base_price, Decimal("46.44"))

    def test_recalculate_uses_max_supplier_price_after_conversion(self):
        CurrencyRate.objects.create(
            currency="RUB",
            rate_to_BYN=Decimal("0.038700"),
        )

        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-BYN-001",
            supplier_price=Decimal("100"),
            currency="BYN",
            stock_quantity=10,
            lead_time_days=0,
        )

        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-RUB-001",
            supplier_price=Decimal("3000"),
            currency="RUB",
            stock_quantity=10,
            lead_time_days=3,
        )

        CurrencyService.update_product_base_price(self.product)

        self.product.refresh_from_db()

        # 3000 RUB * 0.0387 = 116.10 BYN
        # 116.10 + 20% = 139.32 BYN
        self.assertEqual(self.product.base_price, Decimal("139.32"))

    def test_missing_currency_rate_raises_error(self):
        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-USD-001",
            supplier_price=Decimal("100"),
            currency="USD",
            stock_quantity=10,
            lead_time_days=3,
        )

        with self.assertRaises(ValueError):
            CurrencyService.update_product_base_price(self.product)