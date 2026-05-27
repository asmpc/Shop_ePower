from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shop_epower.orders.models import Order, OrderStatus


User = get_user_model()


class TestsManagerOrderViews(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            email="frontend-manager@example.com",
            username="frontend-manager",
            password="testpass123",
            role="manager",
        )

        self.client_user = User.objects.create_user(
            email="frontend-client@example.com",
            username="frontend-client",
            password="testpass123",
            role="client",
        )

        self.order = Order.objects.create(
            user=self.client_user,
            status=OrderStatus.PROCESSING,
            is_legal_entity=False,
            customer_name="Frontend Client",
            customer_email="frontend-client@example.com",
            customer_phone="+10000000040",
            total_price=Decimal("100.00"),
        )

    # Проверяем manager detail page:
    # для заказа в статусе PROCESSING
    # отображаются кнопки Complete order и Cancel order.
    def test_manager_detail_page_shows_cancel_button_for_processing_order(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complete order")
        self.assertContains(response, "Cancel order")

    # Проверяем manager frontend workflow:
    # менеджер может отменить заказ
    # в статусе PROCESSING через frontend form.
    def test_manager_can_cancel_processing_order_from_frontend(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:manager_order_status_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "status": OrderStatus.CANCELLED,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.CANCELLED,
        )