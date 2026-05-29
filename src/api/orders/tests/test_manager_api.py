from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient

from shop_epower.orders.models import Order, OrderStatus


User = get_user_model()


class TestsManagerOrdersAPI(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.manager = User.objects.create_user(
            email="manager-api@example.com",
            username="manager-api",
            password="testpass123",
            role="manager",
        )

        self.client_user = User.objects.create_user(
            email="client-api@example.com",
            username="client-api",
            password="testpass123",
            role="client",
        )

        self.order = Order.objects.create(
            user=self.client_user,
            status=OrderStatus.NEW,
            is_legal_entity=False,
            customer_name="Client API",
            customer_email="client-api@example.com",
            customer_phone="+10000000020",
            total_price=Decimal("100.00"),
        )

    # Проверяем manager orders list API:
    # менеджер может получить список всех заказов.
    def test_manager_can_get_orders_list(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            "/api/orders/manage/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.order.id)

    # Проверяем permissions manager list API:
    # обычный клиент не может получить manager orders endpoint.
    def test_client_cannot_get_manager_orders_list(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.get(
            "/api/orders/manage/",
        )

        self.assertEqual(response.status_code, 403)

    # Проверяем manager workflow API:
    # менеджер может перевести заказ
    # из статуса NEW в статус PROCESSING.
    def test_manager_can_move_order_from_new_to_processing(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f"/api/orders/manage/{self.order.id}/status/",
            {
                "status": OrderStatus.PROCESSING,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )

    # Проверяем manager workflow API:
    # менеджер может перевести заказ
    # из статуса PROCESSING в статус COMPLETED.
    def test_manager_can_move_order_from_processing_to_completed(self):
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f"/api/orders/manage/{self.order.id}/status/",
            {
                "status": OrderStatus.COMPLETED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.COMPLETED,
        )

    # Проверяем ограничения manager workflow API:
    # заказ нельзя перевести напрямую
    # из статуса NEW в статус COMPLETED.
    def test_manager_cannot_make_invalid_transition(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f"/api/orders/manage/{self.order.id}/status/",
            {
                "status": OrderStatus.COMPLETED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.NEW,
        )

    # Проверяем permissions manager workflow API:
    # обычный клиент не может изменять статус заказа.
    def test_client_cannot_update_order_status(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.post(
            f"/api/orders/manage/{self.order.id}/status/",
            {
                "status": OrderStatus.PROCESSING,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.NEW,
        )

    # Проверяем manager cancel API:
    # менеджер может отменить заказ
    # в статусе PROCESSING через manager endpoint.
    def test_manager_can_cancel_processing_order(self):
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f"/api/orders/manage/{self.order.id}/status/",
            {
                "status": OrderStatus.CANCELLED,
                "cancellation_reason": "supplier_unavailable",
                "cancellation_comment": "Supplier failed to ship.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.CANCELLED,
        )
        self.assertEqual(
            self.order.cancellation_reason,
            "supplier_unavailable",
        )

        self.assertEqual(
            self.order.cancellation_comment,
            "Supplier failed to ship.",
        )