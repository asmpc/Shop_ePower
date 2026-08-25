from decimal import Decimal

from django.test import TestCase

from rest_framework.test import APIClient

from shop_epower.orders.services import (
    create_order_from_cart,
)

from shop_epower.cart.tests.helpers import (
    create_test_cart_with_item,
)

from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)

from shop_epower.catalog.tests.helpers import (
    create_test_product,
)

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)

from shop_epower.payments.tests.helpers import (
    create_test_payment,
)


class TestsClientPaymentListAPI(TestCase):

    def setUp(self):

        self.client = APIClient()

        self.user = create_test_user(
            email='payment-client@test.com',
            username='payment-client',
        )

        self.other_user = create_test_user(
            email='other-payment-client@test.com',
            username='other-payment-client',
        )

    def create_payment_for_user(
        self,
        *,
        user,
        prefix,
    ):
        product = create_test_product(
            name=f'{prefix} Product',
            brand_name=f'{prefix} Brand',
            category_name=f'{prefix} Category',
            manufacturer_article=f'{prefix}-001',
            base_price=Decimal('100.00'),
        )

        supplier = create_test_supplier(
            name=f'{prefix} Supplier',
        )

        create_test_supplier_product(
            supplier=supplier,
            product=product,
            supplier_article=f'SUP-{prefix}-001',
            stock_quantity=10,
        )

        cart = create_test_cart_with_item(
            user=user,
            product=product,
            quantity=1,
            price_snapshot=Decimal('100.00'),
        )

        order = create_order_from_cart(
            user=user,
            cart=cart,
        )

        return create_test_payment(
            order=order,
            amount=Decimal('100.00'),
        )

    # Проверяем, что клиент видит только платежи
    # собственных заказов.
    def test_client_payment_list_returns_only_own_payments(self):

        own_payment = self.create_payment_for_user(
            user=self.user,
            prefix='OWN-PAYMENT',
        )

        other_payment = self.create_payment_for_user(
            user=self.other_user,
            prefix='OTHER-PAYMENT',
        )

        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            '/api/payments/my/',
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        payment_ids = [
            payment['id']
            for payment in response.data
        ]

        self.assertIn(
            own_payment.id,
            payment_ids,
        )

        self.assertNotIn(
            other_payment.id,
            payment_ids,
        )