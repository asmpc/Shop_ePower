from django.test import TestCase
from django.urls import reverse

from shop_epower.orders.tests.helpers import (
    create_test_product,
    create_test_supplier,
    create_test_supplier_product,
)


class TestsProductListInventory(TestCase):

    # Проверяем, что карточка товара в каталоге
    # показывает точное количество товара
    # на собственном складе.
    def test_product_list_displays_own_stock_quantity(self):

        product = create_test_product(
            name="Own Stock Product",
            manufacturer_article="OWN-STOCK-001",
            base_price="99.00",
        )

        own_supplier = create_test_supplier(
            name="Own Warehouse",
            is_own=True,
        )

        create_test_supplier_product(
            supplier=own_supplier,
            product=product,
            supplier_article="SUP-OWN-STOCK-001",
            stock_quantity=17,
        )

        response = self.client.get(
            reverse("catalog:product_list"),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "In stock:",
        )

        self.assertRegex(
            response.content.decode(),
            r"In stock:\s*17",
        )

    # Проверяем, что карточка товара показывает
    # количество товара под заказ
    # и минимальный срок поставки.
    def test_product_list_displays_supplier_stock(self):
        product = create_test_product(
            name="Supplier Product",
            manufacturer_article="SUPPLIER-001",
            base_price="99.00",
        )

        supplier = create_test_supplier(
            name="External Supplier",
            is_own=False,
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-001",
            stock_quantity=42,
            lead_time_days=5,
        )

        response = self.client.get(
            reverse("catalog:product_list"),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Available to order:",
        )

        self.assertRegex(
            response.content.decode(),
            r"Available to order:\s*42",
        )

        self.assertRegex(
            response.content.decode(),
            r"from\s*5\s*days",
        )

    # Проверяем, что карточка товара показывает
    # "Out of stock", если товара нет
    # ни на собственном складе, ни у поставщиков.
    def test_product_list_displays_out_of_stock(self):
        product = create_test_product(
            name="Out Of Stock Product",
            manufacturer_article="OUT-001",
            base_price="99.00",
        )

        own_supplier = create_test_supplier(
            name="Own Warehouse",
            is_own=True,
        )

        create_test_supplier_product(
            supplier=own_supplier,
            product=product,
            supplier_article="SUP-OUT-001",
            stock_quantity=0,
        )

        supplier = create_test_supplier(
            name="External Supplier",
            is_own=False,
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article="SUP-OUT-002",
            stock_quantity=0,
            lead_time_days=5,
        )

        response = self.client.get(
            reverse("catalog:product_list"),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Out of stock",
        )

        self.assertNotContains(
            response,
            "Available to order:",
        )

        self.assertNotContains(
            response,
            "In stock:",
        )