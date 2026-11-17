from decimal import Decimal
from urllib.parse import quote, urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderItem, OrderStatus
from shop_epower.orders.services import (
    assign_order_funds,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.choices import PaymentMethod
from shop_epower.payments.services import record_manual_order_payment


class TestsManagerUnpaidOrderListViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )

        self.product = create_test_product()
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

        self.url = reverse("orders:manager_unpaid_order_list")

    def _create_unpaid_shipments(self, *, count):
        shipments = []

        for _ in range(count):
            order = create_test_order(
                user=self.user,
                customer_account=self.account,
                status=OrderStatus.PROCESSING,
                total_price=Decimal("100.00"),
            )
            OrderItem.objects.create(
                order=order,
                product=self.product,
                product_name=self.product.name,
                unit_price=Decimal("100.00"),
                quantity=1,
                total_price=Decimal("100.00"),
                currency_snapshot=order.currency_snapshot,
            )
            shipment = complete_order_shipment(
                order=order,
                created_by=self.manager,
            )
            shipments.append(shipment)

        return shipments

    # Авторизованный клиент не может открыть служебный список долгов.
    def test_client_cannot_open_unpaid_order_list(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    # Менеджер сразу видит непогашенный отгруженный заказ.
    # Для первоначального списка вводить фильтры не требуется.
    def test_manager_sees_unpaid_shipment_without_filters(self):
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unpaid shipped orders")
        self.assertContains(response, self.user.email)
        self.assertContains(response, f"Order #{self.order.pk}")
        self.assertContains(
            response,
            f"Remaining debt: 100.00 {shipment.currency_snapshot}",
        )

    # Администратор видит непогашенные отгрузки сразу при открытии.
    def test_admin_sees_unpaid_shipment_without_filters(self):
        admin = create_test_admin()
        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )
        self.client.force_login(admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"Order #{self.order.pk}",
        )

    # Гость направляется на вход с сохранением адреса списка.
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)

        login_url = reverse("accounts:login")

        self.assertRedirects(
            response,
            f"{login_url}?next={self.url}",
            fetch_redirect_response=False,
        )

    # На первой странице показаны 20 отгрузок, на второй — одна.
    # Переходы доступны, записи не теряются и не повторяются.
    def test_unpaid_order_list_is_paginated(self):
        shipments = self._create_unpaid_shipments(count=21)
        self.client.force_login(self.manager)

        first_page = self.client.get(self.url)

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["shipments"]), 20)
        self.assertEqual(
            first_page.context["page_obj"].paginator.count,
            21,
        )
        self.assertContains(first_page, 'href="?page=2"')

        second_page = self.client.get(
            self.url,
            {"page": 2},
        )

        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(second_page.context["shipments"]), 1)
        self.assertContains(second_page, 'href="?page=1"')

        shown_ids = [
            shipment.pk
            for shipment in first_page.context["shipments"]
        ] + [
            shipment.pk
            for shipment in second_page.context["shipments"]
        ]

        self.assertCountEqual(
            shown_ids,
            [shipment.pk for shipment in shipments],
        )

    # Страница показывает погашение и остаток каждого заказа отдельно.
    # Общий долг счёта не подставляется в строки заказов.
    def test_list_displays_debt_separately_for_each_order(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="unpaid:view:receipt",
            created_by=self.manager,
        )
        assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="unpaid:view:assignment",
            created_by=self.manager,
        )
        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self._create_unpaid_shipments(count=1)
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        currency = self.account.currency

        self.assertContains(
            response,
            f"Applied funds: 60.00 {currency}",
        )
        self.assertContains(
            response,
            f"Remaining debt: 40.00 {currency}",
        )
        self.assertContains(
            response,
            f"Remaining debt: 100.00 {currency}",
        )

    # Менеджер может открыть список долгов прямо из навбара.
    def test_manager_sees_unpaid_orders_link_in_navbar(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("home"),
        )

        self.assertContains(
            response,
            f'href="{self.url}"',
        )
        self.assertContains(
            response,
            "Unpaid shipments",
        )

    # Из меню Finances доступны платежи, счета клиентов и журнал.
    def test_finance_menu_contains_financial_pages(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("home"))

        self.assertContains(response, 'id="finance-menu"')
        self.assertContains(response, 'data-bs-toggle="dropdown"')

        menu_links = (
            ("payments:manager_payment_list", "Payments"),
            ("finance:manager_account_list", "Customer accounts"),
            ("finance:manager_transaction_list", "Transaction journal"),
        )

        for url_name, label in menu_links:
            with self.subTest(url_name=url_name):
                url = reverse(url_name)

                self.assertContains(
                    response,
                    f"""
                    <a class="dropdown-item" href="{url}">
                        {label}
                    </a>
                    """,
                    html=True,
                )

    # Переход в заказ сохраняет email и страницу списка долгов.
    # Кнопка Back возвращает сотрудника к тем же результатам поиска.
    def test_order_navigation_preserves_unpaid_list_page(self):
        self._create_unpaid_shipments(count=21)
        self.client.force_login(self.manager)

        params = {
            "customer_email": self.user.email,
            "page": 2,
        }
        list_url = f"{self.url}?{urlencode(params)}"

        list_response = self.client.get(
            self.url,
            params,
        )

        self.assertEqual(list_response.status_code, 200)

        shipment = list_response.context["shipments"][0]
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": shipment.order_id},
        )

        self.assertContains(
            list_response,
            f'href="{detail_url}?next={quote(list_url)}"',
        )

        detail_response = self.client.get(
            detail_url,
            {"next": list_url},
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(
            detail_response.context["back_url"],
            list_url,
        )
        self.assertContains(
            detail_response,
            f'href="{escape(list_url)}"',
        )

    # Клиент не видит служебные финансовые разделы в навбаре.
    def test_client_does_not_see_staff_financial_navigation(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, 'id="finance-menu"')

        staff_routes = (
            "orders:manager_unpaid_order_list",
            "payments:manager_payment_list",
            "finance:manager_account_list",
            "finance:manager_transaction_list",
        )

        for url_name in staff_routes:
            with self.subTest(url_name=url_name):
                self.assertNotContains(
                    response,
                    f'href="{reverse(url_name)}"',
                )

    # Поиск по email сужает список и сохраняет введённое значение.
    # При отсутствии совпадений показывается пустой результат.
    def test_email_search_filters_list_and_preserves_input(self):
        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )
        self.client.force_login(self.manager)
        email_query = "missing@example.com"

        response = self.client.get(
            self.url,
            {"customer_email": email_query},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["shipments"]),
            [],
        )
        self.assertContains(response, 'name="customer_email"')
        self.assertContains(
            response,
            f'value="{email_query}"',
        )
        self.assertContains(
            response,
            "No unpaid shipped orders.",
        )

    # Переходы между страницами сохраняют условие поиска по email.
    # Введённое значение остаётся в форме.
    def test_email_filter_is_preserved_in_pagination(self):
        self._create_unpaid_shipments(count=21)
        self.client.force_login(self.manager)
        email_query = self.user.email

        first_page = self.client.get(
            self.url,
            {"customer_email": email_query},
        )

        next_query = urlencode(
            {
                "customer_email": email_query,
                "page": 2,
            }
        )

        self.assertEqual(len(first_page.context["shipments"]), 20)
        self.assertContains(
            first_page,
            f'href="{escape("?" + next_query)}"',
        )

        second_page = self.client.get(
            self.url,
            {
                "customer_email": email_query,
                "page": 2,
            },
        )

        previous_query = urlencode(
            {
                "customer_email": email_query,
                "page": 1,
            }
        )

        self.assertEqual(len(second_page.context["shipments"]), 1)
        self.assertContains(
            second_page,
            f'href="{escape("?" + previous_query)}"',
        )
        self.assertContains(
            second_page,
            f'value="{email_query}"',
        )

    # Номер заказа сужает список до нужной отгрузки.
    # Оба введённых условия поиска сохраняются в форме.
    def test_order_id_search_filters_list_and_preserves_input(self):
        shipments = self._create_unpaid_shipments(count=2)
        matching_shipment = shipments[0]
        order_id = str(matching_shipment.order_id)
        self.client.force_login(self.manager)

        response = self.client.get(
            self.url,
            {
                "customer_email": self.user.email,
                "order_id": order_id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                shipment.pk
                for shipment in response.context["shipments"]
            ],
            [matching_shipment.pk],
        )
        self.assertContains(response, 'name="order_id"')
        self.assertContains(
            response,
            f'value="{order_id}"',
        )
        self.assertContains(
            response,
            f'value="{self.user.email}"',
        )

    # После погашения последнего долга на странице список сокращается.
    # Возврат открывает доступную страницу и сохраняет поиск.
    def test_returns_last_available_page_after_debt_is_paid(self):
        self._create_unpaid_shipments(count=21)
        self.client.force_login(self.manager)

        params = {
            "customer_email": self.user.email,
            "page": 2,
        }
        before = self.client.get(self.url, params)

        self.assertEqual(before.status_code, 200)
        self.assertEqual(len(before.context["shipments"]), 1)

        shipment = before.context["shipments"][0]

        record_manual_order_payment(
            order=shipment.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="unpaid:view:last-page:receipt",
            created_by=self.manager,
        )
        assign_order_funds(
            order=shipment.order,
            amount=Decimal("100.00"),
            operation_key="unpaid:view:last-page:assignment",
            created_by=self.manager,
        )

        after = self.client.get(self.url, params)

        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.context["page_obj"].number, 1)
        self.assertEqual(
            after.context["page_obj"].paginator.count,
            20,
        )
        self.assertEqual(len(after.context["shipments"]), 20)
        self.assertContains(
            after,
            f'value="{self.user.email}"',
        )

    # Список долгов показывает доступные средства счёта зелёным.
    # Поступило 150, заказу назначено 90 — свободно осталось 60.
    def test_list_shows_available_account_funds_in_green(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("150.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="unpaid:view:available:receipt",
            created_by=self.manager,
        )

        assign_order_funds(
            order=self.order,
            amount=Decimal("90.00"),
            operation_key="unpaid:view:available:assignment",
            created_by=self.manager,
        )

        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                '<span class="text-success fw-semibold">'
                f"Available to assign: 60.00 {self.account.currency}"
                "</span>"
            ),
            html=True,
        )
