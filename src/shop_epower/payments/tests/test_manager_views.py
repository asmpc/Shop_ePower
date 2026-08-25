from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PaymentHistory,
)
from shop_epower.payments.tests.helpers import (
    create_test_payment,
    create_test_payment_history,
)
from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
    create_test_admin,
)



class TestsManagerPaymentViews(TestCase):

    def setUp(self):
        self.client_user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
            role="client",
        )

        self.manager = create_test_manager(
            email="manager@test.com",
            username="manager",
            password="testpass123",
        )

        self.admin = create_test_admin(
            email="admin@test.com",
            username="admin",
            password="testpass123",
        )

        self.order = create_test_order(
            user=self.client_user,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="",
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.MANUAL,
            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

    # Проверяем, что менеджер может открыть список оплат.
    def test_manager_can_open_payment_list(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse("payments:manager_payment_list"),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            self.payment,
            response.context["payments"],
        )

    # Проверяем, что администратор может открыть список оплат.
    def test_admin_can_open_payment_list(self):
        self.client.force_login(
            self.admin,
        )

        response = self.client.get(
            reverse("payments:manager_payment_list"),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            self.payment,
            response.context["payments"],
        )

    # Проверяем, что клиент не видит оплаты в manager list.
    def test_client_cannot_see_payment_list(self):
        self.client.force_login(
            self.client_user,
        )

        response = self.client.get(
            reverse("payments:manager_payment_list"),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            list(response.context["payments"]),
            [],
        )

    # Проверяем сохранение выбранных фильтров.
    def test_selected_filters_are_saved_in_context(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse("payments:manager_payment_list"),
            {
                "status": "paid",
                "method": "online",
                "provider": "mock",
            },
        )

        self.assertEqual(
            response.context["selected_status"],
            "paid",
        )

        self.assertEqual(
            response.context["selected_method"],
            "online",
        )

        self.assertEqual(
            response.context["selected_provider"],
            "mock",
        )

    # Проверяем, что менеджер может открыть detail оплаты.
    def test_manager_can_open_payment_detail(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                args=[self.payment.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context["payment"],
            self.payment,
        )

    # Проверяем, что администратор может открыть detail оплаты.
    def test_admin_can_open_payment_detail(self):
        self.client.force_login(
            self.admin,
        )

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                args=[self.payment.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context["payment"],
            self.payment,
        )

    # Проверяем, что клиент не может открыть detail оплаты.
    def test_client_cannot_open_payment_detail(self):
        self.client.force_login(
            self.client_user,
        )

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                args=[self.payment.id],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    # Проверяем, что detail страницы оплаты показывает историю изменений.
    def test_payment_detail_shows_payment_history(self):
        create_test_payment_history(
            payment=self.payment,
            old_status=PaymentStatus.PENDING,
            new_status=PaymentStatus.PAID,
            comment="Invoice paid.",
            changed_by=self.manager,
        )

        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                args=[self.payment.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Payment history",
        )

        self.assertContains(
            response,
            "Invoice paid.",
        )

        self.assertContains(
            response,
            self.manager.username,
        )

        self.assertContains(
            response,
            "PENDING",
        )

        self.assertContains(
            response,
            "PAID",
        )

    # Проверяем, что manager action сохраняет пользователя
    # в PaymentHistory.changed_by.
    def test_manager_payment_action_creates_history_with_changed_by(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:manager_mark_payment_paid",
                args=[self.order.id],
            ),
            {
                "manager_comment": "Invoice received",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        history = PaymentHistory.objects.get(
            payment=self.payment,
        )

        self.assertEqual(
            history.changed_by,
            self.manager,
        )

        self.assertEqual(
            history.new_status,
            PaymentStatus.PAID,
        )
