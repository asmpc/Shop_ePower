from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import (
    create_test_order,
    create_test_order_item_change,
)


class TestsCustomerOrderChangeIndicatorViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
        )

    # Если позиции заказа изменялись, клиентская страница
    # получает признак для отображения соответствующей отметки.
    def test_order_detail_marks_order_with_item_changes(self):
        create_test_order_item_change(
            order=self.order,
            changed_by=self.manager,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "orders:detail",
                kwargs={"order_id": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context["has_item_changes"], True)

    # У клиента два заказа; изменялся только другой.
    # Просматриваемый заказ получает признак False.
    def test_other_order_changes_do_not_mark_unchanged_order(self):
        other_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
        )
        create_test_order_item_change(
            order=other_order,
            changed_by=self.manager,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "orders:detail",
                kwargs={"order_id": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context["has_item_changes"], False)
        self.assertNotContains(response, "Order updated")

    # Клиент видит отметку об изменении перед информацией заказа.
    # Внутренняя причина изменения в страницу не попадает.
    def test_order_detail_displays_change_notice_without_private_reason(self):
        change = create_test_order_item_change(
            order=self.order,
            changed_by=self.manager,
            reason="Internal reason visible to staff only.",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "orders:detail",
                kwargs={"order_id": self.order.pk},
            ),
        )

        self.assertContains(response, "Order updated")
        self.assertNotContains(response, change.reason)

        html = response.content.decode()

        self.assertLess(
            html.index("Order updated"),
            html.index("Order information"),
        )

    # Список содержит изменённый и неизменённый заказы клиента.
    # Каждый получает свой признак без дополнительных запросов
    # при чтении уже загруженных строк.
    def test_order_list_marks_only_changed_orders_without_extra_queries(self):
        unchanged_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
        )
        create_test_order_item_change(
            order=self.order,
            changed_by=self.manager,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("orders:list"))

        self.assertEqual(response.status_code, 200)

        orders = list(response.context["orders"])

        with self.assertNumQueries(0):
            flags = {
                order.pk: order.has_item_changes
                for order in orders
            }

        self.assertEqual(
            flags,
            {
                self.order.pk: True,
                unchanged_order.pk: False,
            },
        )

    # Отметка находится рядом со статусом изменённого заказа.
    # Соседний заказ остаётся без отметки; причина скрыта.
    def test_order_list_displays_badge_only_for_changed_order(self):
        unchanged_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
        )
        change = create_test_order_item_change(
            order=self.order,
            changed_by=self.manager,
            reason="Internal reason visible to staff only.",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("orders:list"))

        self.assertContains(response, f"Order #{unchanged_order.pk}")
        self.assertContains(response, "Order updated", count=1)
        self.assertNotContains(response, change.reason)
        self.assertContains(
            response,
            f"""
            <div class="col-md-3 mb-3 mb-md-0">
                <span class="h5 mb-0">
                    Order #{self.order.pk}
                </span>
                <span class="badge bg-primary ms-2">PROCESSING</span>
                <span class="badge bg-info text-dark ms-2">
                    Order updated
                </span>
            </div>
            """,
            html=True,
        )

    # Изменённый заказ другого клиента отсутствует в My Orders.
    # Прямое открытие его карточки возвращает 404.
    def test_client_cannot_view_another_customers_changed_order(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(user=other_user)
        other_order = create_test_order(
            user=other_user,
            customer_account=other_account,
            status=OrderStatus.PROCESSING,
        )
        change = create_test_order_item_change(
            order=other_order,
            changed_by=self.manager,
            reason="Private reason for another customer's order.",
        )
        self.client.force_login(self.user)

        detail_response = self.client.get(
            reverse(
                "orders:detail",
                kwargs={"order_id": other_order.pk},
            ),
        )

        self.assertEqual(detail_response.status_code, 404)

        list_response = self.client.get(reverse("orders:list"))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [order.pk for order in list_response.context["orders"]],
            [self.order.pk],
        )
        self.assertNotContains(list_response, change.reason)
        self.assertNotContains(list_response, "Order updated")

    # Несколько изменений не дублируют заказ в списке.
    # Отметка работает на второй странице выбранного статуса.
    # Открытие заказа и возврат сохраняют фильтр и страницу.
    def test_changed_order_keeps_filter_and_page_when_opened_from_list(self):
        for _ in range(20):
            create_test_order(
                user=self.user,
                customer_account=self.account,
                status=OrderStatus.PROCESSING,
            )

        for _ in range(2):
            create_test_order_item_change(
                order=self.order,
                changed_by=self.manager,
            )

        excluded_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.NEW,
        )
        create_test_order_item_change(
            order=excluded_order,
            changed_by=self.manager,
        )

        self.client.force_login(self.user)
        list_url = reverse("orders:list")

        first_response = self.client.get(
            list_url,
            {"status": OrderStatus.PROCESSING},
        )

        self.assertEqual(first_response.status_code, 200)

        first_page = first_response.context["orders"]

        self.assertEqual(first_page.paginator.count, 21)
        self.assertEqual(len(first_page), 20)
        self.assertNotContains(first_response, "Order updated")

        query_string = urlencode(
            {"status": OrderStatus.PROCESSING, "page": 2},
        )
        self.assertContains(
            first_response,
            f'href="?{escape(query_string)}"',
        )

        second_response = self.client.get(
            f"{list_url}?{query_string}",
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            [order.pk for order in second_response.context["orders"]],
            [self.order.pk],
        )
        self.assertContains(second_response, "Order updated", count=1)

        detail_url = (
            reverse(
                "orders:detail",
                kwargs={"order_id": self.order.pk},
            )
            + "?"
            + query_string
        )
        self.assertContains(
            second_response,
            f'href="{escape(detail_url)}"',
        )

        detail_response = self.client.get(detail_url)

        self.assertContains(detail_response, "Order updated")
        self.assertContains(
            detail_response,
            f'href="{escape(f"{list_url}?{query_string}")}"',
        )
