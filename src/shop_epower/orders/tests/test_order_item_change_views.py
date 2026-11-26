from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import (
    create_test_order,
    create_test_order_item_change,
)


class TestsManagerOrderItemChangeViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )
        self.change = create_test_order_item_change(
            order=self.order,
            changed_by=self.manager,
        )

    # Страница сотрудника получает историю выбранного заказа.
    # История подготовлена с пагинацией по 20 записей.
    def test_order_detail_contains_paginated_item_changes(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)

        page = response.context["item_changes"]

        self.assertEqual(page.number, 1)
        self.assertEqual(page.paginator.per_page, 20)
        self.assertEqual(page.paginator.count, 1)
        self.assertEqual(list(page), [self.change])

    # История изменений изначально свёрнута.
    # Внутри доступны сохранённое название товара, причина и автор.
    def test_item_change_history_is_collapsed_by_default(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertContains(
            response,
            """
            <button
                class="btn btn-outline-secondary btn-sm collapsed"
                type="button"
                data-bs-toggle="collapse"
                data-bs-target="#order-item-change-history"
                aria-expanded="false"
                aria-controls="order-item-change-history"
            >
                Change history
            </button>
            """,
            html=True,
        )
        self.assertContains(
            response,
            '<div class="collapse" id="order-item-change-history">',
        )
        self.assertContains(response, self.change.product_name)
        self.assertContains(response, self.change.reason)
        self.assertContains(
            response,
            f"""
            <p class="mb-1">
                <strong>Changed by:</strong>
                {self.manager.username}
            </p>
            """,
            html=True,
        )

    # История показывает по 20 изменений на странице.
    # Переходы сохраняют фильтр исходного списка заказов,
    # а сама история после перехода остаётся раскрытой.
    def test_item_change_history_pagination_preserves_list_context(self):
        for number in range(20):
            create_test_order_item_change(
                order=self.order,
                changed_by=self.manager,
                product_name=f"Changed product {number}",
            )

        self.client.force_login(self.manager)

        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )
        list_url = (
            reverse("orders:manager_order_list")
            + "?"
            + urlencode({"status": self.order.status, "page": 3})
        )

        first_response = self.client.get(
            detail_url,
            {"next": list_url},
        )

        self.assertEqual(first_response.status_code, 200)

        first_page = first_response.context["item_changes"]

        self.assertEqual(first_page.paginator.count, 21)
        self.assertEqual(len(first_page), 20)
        self.assertNotIn(self.change, list(first_page))

        next_link = (
            detail_url
            + "?"
            + urlencode({"next": list_url, "changes_page": 2})
            + "#order-item-change-history"
        )
        self.assertContains(
            first_response,
            f'href="{escape(next_link)}"',
        )

        second_response = self.client.get(next_link)

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            list(second_response.context["item_changes"]),
            [self.change],
        )
        self.assertEqual(second_response.context["back_url"], list_url)
        self.assertContains(
            second_response,
            '<div class="collapse show" id="order-item-change-history">',
        )

        previous_link = (
            detail_url
            + "?"
            + urlencode({"next": list_url, "changes_page": 1})
            + "#order-item-change-history"
        )
        self.assertContains(
            second_response,
            f'href="{escape(previous_link)}"',
        )

    # Администратор видит историю заказа.
    # Автор записи — менеджер, который выполнил изменение.
    def test_admin_sees_history_with_original_author(self):
        admin = create_test_admin()
        self.client.force_login(admin)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["item_changes"]),
            [self.change],
        )
        self.assertContains(response, self.change.reason)
        self.assertContains(
            response,
            f"""
            <p class="mb-1">
                <strong>Changed by:</strong>
                {escape(self.manager.username)}
            </p>
            """,
            html=True,
        )

    # Клиенту запрещён доступ к странице сотрудника.
    # В собственном заказе внутренняя история и причины не отображаются.
    def test_client_cannot_view_internal_item_change_history(self):
        self.client.force_login(self.user)

        staff_response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
            {"changes_page": 1},
        )

        self.assertEqual(staff_response.status_code, 403)
        self.assertNotContains(
            staff_response,
            self.change.reason,
            status_code=403,
        )

        customer_response = self.client.get(
            reverse(
                "orders:detail",
                kwargs={"order_id": self.order.pk},
            ),
        )

        self.assertEqual(customer_response.status_code, 200)
        self.assertNotContains(customer_response, self.change.reason)
        self.assertNotContains(
            customer_response,
            'id="order-item-change-history"',
        )