from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.cart.tests.helpers import (
    create_test_cart_with_item,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.orders.models import Order
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
)
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
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

    # Проверяем, что пользователь с неполным профилем
    # не может оформить заказ.
    def test_checkout_with_incomplete_profile_redirects_to_profile_edit(self):

        self.user.first_name = ''
        self.user.save(
            update_fields=['first_name'],
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            reverse("orders:checkout"),
            data={
                "delivery_method": "pickup",
                "payment_method": PaymentMethod.ON_RECEIPT,
            },
        )

        profile_edit_url = reverse(
            "accounts:profile_edit",
        )

        cart_url = reverse(
            "cart-detail",
        )

        expected_url = (
            f"{profile_edit_url}?"
            f"{urlencode({'next': cart_url})}"
        )

        self.assertRedirects(
            response,
            expected_url,
            fetch_redirect_response=False,
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

    # Проверяем, что гость при попытке оформить заказ
    # перенаправляется на вход с возвратом в корзину.
    def test_guest_checkout_redirects_to_login_with_cart_next(self):
        response = self.client.post(
            reverse(
                "orders:checkout",
            ),
        )

        expected_url = (
            f"{reverse('accounts:login')}"
            f"?next={reverse('cart-detail')}"
        )

        self.assertRedirects(
            response,
            expected_url,
            fetch_redirect_response=False,
        )