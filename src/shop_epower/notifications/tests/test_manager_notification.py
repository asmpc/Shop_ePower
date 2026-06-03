from decimal import Decimal

from django.core import mail
from django.test import TestCase

from shop_epower.notifications.services import (
    send_order_created_notification_to_managers,
)

from .helpers import (
    create_test_order,
    create_test_user,
)


class TestManagerOrderNotification(TestCase):

    # Проверяем, что менеджеры получают уведомление
    # после создания нового заказа.
    def test_send_order_created_notification_to_managers(self):
        manager1 = create_test_user(
            email="manager1@test.com",
            username="manager1",
            role="manager",
            is_staff=True,
        )

        manager2 = create_test_user(
            email="manager2@test.com",
            username="manager2",
            role="manager",
            is_staff=True,
        )

        client = create_test_user(
            email="client@test.com",
            username="client",
            role="client",
        )

        order = create_test_order(
            user=client,
            total_price=Decimal("321.00"),
        )

        send_order_created_notification_to_managers(order)

        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        self.assertIn(manager1.email, email.to)
        self.assertIn(manager2.email, email.to)

        self.assertIn(
            f"Order #{order.id}",
            email.subject,
        )

        self.assertIn(
            str(order.total_price),
            email.body,
        )

        self.assertIn(
            order.customer_email,
            email.body,
        )