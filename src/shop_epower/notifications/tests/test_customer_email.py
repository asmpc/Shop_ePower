from decimal import Decimal

from django.core import mail
from django.test import TestCase

from shop_epower.notifications.services import (
    send_order_created_email_to_customer,
)

from .helpers import (
    create_test_order,
    create_test_user,
)


class TestCustomerOrderEmail(TestCase):

    # Проверяем, что клиент получает email
    # после успешного создания заказа.
    def test_send_order_created_email_to_customer(self):
        user = create_test_user(
            email="client@test.com",
            username="client",
            role="client",
        )

        order = create_test_order(
            user=user,
            total_price=Decimal("123.45"),
        )

        send_order_created_email_to_customer(order)

        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        self.assertIn(
            order.customer_email,
            email.to,
        )

        self.assertIn(
            f"Order #{order.id}",
            email.subject,
        )

        self.assertIn(
            str(order.total_price),
            email.body,
        )

        self.assertIn(
            order.customer_name,
            email.body,
        )