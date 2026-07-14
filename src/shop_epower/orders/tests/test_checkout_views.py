from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shop_epower.orders.models import Order
from shop_epower.orders.tests.helpers import (
    create_test_user,
    create_test_product,
    create_test_supplier,
    create_test_supplier_product,
    create_test_cart_with_item,
)
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
)


class TestsCheckoutViews(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="checkout-view@example.com",
            username="checkout-view",
            phone="+10000000050",
        )

        self.product = create_test_product(
            name="Checkout View Product",
            brand_name="Checkout View Brand",
            category_name="Checkout View Category",
            manufacturer_article="CHECKOUT-VIEW-001",
            base_price=Decimal("100.00"),
        )

        self.supplier = create_test_supplier(
            name="Checkout View Supplier",
        )

        create_test_supplier_product(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-CHECKOUT-VIEW-001",
            stock_quantity=10,
        )

        self.cart = create_test_cart_with_item(
            user=self.user,
            product=self.product,
            quantity=1,
            price_snapshot=Decimal("100.00"),
        )

    # Проверяем временное ограничение online payment:
    # заказ и payment не должны создаваться,
    # пока интеграция с платежными сервисами не подключена.
    def test_checkout_with_online_payment_does_not_create_order(self):
        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            reverse("orders:checkout"),
            data={
                "delivery_method": "pickup",
                "payment_method": PaymentMethod.ONLINE,
            },
        )

        self.assertRedirects(
            response,
            reverse("cart-detail"),
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

        self.assertEqual(
            Payment.objects.count(),
            0,
        )

        self.cart.refresh_from_db()

        self.assertTrue(
            self.cart.is_active,
        )