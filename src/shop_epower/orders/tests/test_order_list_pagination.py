from urllib.parse import quote

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import create_test_order


class TestsCustomerOrderListPagination(TestCase):
    # Клиент видит не больше 20 заказов на одной странице.
    def test_customer_order_list_is_paginated(self):
        user = create_test_user()

        for _ in range(21):
            create_test_order(user=user)

        self.client.force_login(user)
        url = reverse("orders:list")

        first_page = self.client.get(url)
        second_page = self.client.get(url, {"page": 2})

        self.assertEqual(len(first_page.context["orders"]), 20)
        self.assertEqual(len(second_page.context["orders"]), 1)

    # Переход между страницами сохраняет фильтр по статусу.
    def test_customer_order_pagination_preserves_status_filter(self):
        user = create_test_user()

        for _ in range(21):
            create_test_order(user=user, status=OrderStatus.PROCESSING)

        create_test_order(user=user, status=OrderStatus.CANCELLED)

        self.client.force_login(user)
        url = reverse("orders:list")

        first_page = self.client.get(url, {"status": "processing"})
        second_page = self.client.get(
            url,
            {"status": "processing", "page": 2},
        )

        self.assertEqual(len(first_page.context["orders"]), 20)
        self.assertEqual(len(second_page.context["orders"]), 1)
        self.assertContains(
            first_page,
            'href="?status=processing&amp;page=2"',
        )
        self.assertContains(
            second_page,
            'href="?status=processing&amp;page=1"',
        )

    # Из отфильтрованного списка заказ открывается с контекстом,
    # а кнопка Back возвращает к тому же фильтру и странице.
    def test_back_to_my_orders_preserves_filter_and_page(self):
        user = create_test_user()

        for _ in range(21):
            create_test_order(user=user, status=OrderStatus.PROCESSING)

        self.client.force_login(user)
        list_url = reverse("orders:list")
        list_response = self.client.get(
            list_url,
            {"status": "processing", "page": 2},
        )

        order = list_response.context["orders"][0]
        detail_url = reverse("orders:detail", args=[order.pk])

        self.assertContains(
            list_response,
            f'href="{detail_url}?status=processing&amp;page=2"',
        )

        detail_response = self.client.get(
            detail_url,
            {"status": "processing", "page": 2},
        )
        self.assertContains(
            detail_response,
            f'href="{list_url}?status=processing&amp;page=2"',
        )

    # После отмены заказа сохраняются фильтр и страница списка.
    def test_cancel_order_preserves_list_context(self):
        user = create_test_user()

        for _ in range(22):
            create_test_order(user=user, status=OrderStatus.NEW)

        self.client.force_login(user)
        list_response = self.client.get(
            reverse("orders:list"),
            {"status": "new", "page": 2},
        )
        order = list_response.context["orders"][0]

        detail_url = reverse("orders:detail", args=[order.pk])
        cancel_url = reverse("orders:cancel", args=[order.pk])

        detail_response = self.client.get(
            detail_url,
            {"status": "new", "page": 2},
        )
        self.assertContains(
            detail_response,
            f'action="{cancel_url}?status=new&amp;page=2"',
        )

        cancel_response = self.client.post(
            f"{cancel_url}?status=new&page=2",
        )

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(cancel_response.status_code, 302)
        self.assertEqual(
            cancel_response["Location"],
            f"{detail_url}?status=new&page=2",
        )


class TestsManagerOrderListPagination(TestCase):
    # Список менеджера показывает 20 заказов на первой странице
    # и оставшийся заказ — на второй.
    def test_manager_order_list_is_paginated(self):
        customer = create_test_user()
        manager = create_test_manager()

        for _ in range(21):
            create_test_order(user=customer)

        self.client.force_login(manager)
        url = reverse("orders:manager_order_list")

        first_page = self.client.get(url)
        second_page = self.client.get(url, {"page": 2})

        self.assertEqual(len(first_page.context["orders"]), 20)
        self.assertEqual(len(second_page.context["orders"]), 1)

    # Ссылка на следующую страницу сохраняет выбранный статус.
    def test_manager_order_pagination_preserves_status_filter(self):
        customer = create_test_user()
        manager = create_test_manager()

        for _ in range(21):
            create_test_order(
                user=customer,
                status=OrderStatus.PROCESSING,
            )

        create_test_order(
            user=customer,
            status=OrderStatus.CANCELLED,
        )

        self.client.force_login(manager)
        url = reverse("orders:manager_order_list")

        first_page = self.client.get(url, {"status": "processing"})
        second_page = self.client.get(
            url,
            {"status": "processing", "page": 2},
        )

        self.assertEqual(len(first_page.context["orders"]), 20)
        self.assertEqual(len(second_page.context["orders"]), 1)
        self.assertContains(
            first_page,
            'href="?status=processing&amp;page=2"',
        )

    # Подменённый внешний адрес не должен становиться ссылкой Back.
    def test_manager_order_detail_rejects_external_back_url(self):
        customer = create_test_user()
        manager = create_test_manager()
        order = create_test_order(user=customer)

        self.client.force_login(manager)

        list_url = reverse("orders:manager_order_list")
        detail_url = reverse(
            "orders:manager_order_detail",
            args=[order.pk],
        )

        response = self.client.get(
            detail_url,
            {"next": "https://example.org/fake"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], list_url)

    # Из второй страницы отфильтрованного списка менеджер
    # возвращается к тому же статусу и номеру страницы.
    def test_manager_back_link_preserves_filter_and_page(self):
        customer = create_test_user()
        manager = create_test_manager()

        for _ in range(21):
            create_test_order(
                user=customer,
                status=OrderStatus.PROCESSING,
            )

        self.client.force_login(manager)

        list_url = reverse("orders:manager_order_list")
        list_response = self.client.get(
            list_url,
            {"status": "processing", "page": 2},
        )

        order = list_response.context["orders"][0]
        detail_url = reverse(
            "orders:manager_order_detail",
            args=[order.pk],
        )
        back_url = f"{list_url}?status=processing&page=2"

        self.assertContains(
            list_response,
            f'href="{detail_url}?next={quote(back_url)}"',
        )

        detail_response = self.client.get(
            detail_url,
            {"next": back_url},
        )

        self.assertEqual(detail_response.context["back_url"], back_url)
        self.assertContains(
            detail_response,
            f'href="{list_url}?status=processing&amp;page=2"',
        )

    # Клиенту страница управления заказами недоступна,
    # а не показывается как пустой список.
    def test_client_cannot_open_manager_order_list(self):
        customer = create_test_user()
        self.client.force_login(customer)

        response = self.client.get(
            reverse("orders:manager_order_list"),
        )

        self.assertEqual(response.status_code, 403)

    # Собственный заказ клиент открывает через клиентскую страницу,
    # но менеджерская карточка ему недоступна.
    def test_client_cannot_open_manager_order_detail(self):
        customer = create_test_user()
        order = create_test_order(user=customer)
        self.client.force_login(customer)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                args=[order.pk],
            ),
        )

        self.assertEqual(response.status_code, 403)

    # Чужие заказы не попадают ни в список клиента,
    # ни в общее число страниц его списка.
    def test_customer_order_list_contains_only_own_orders(self):
        customer = create_test_user()
        other_customer = create_test_user()

        own_order = create_test_order(user=customer)

        for _ in range(21):
            create_test_order(user=other_customer)

        self.client.force_login(customer)
        response = self.client.get(reverse("orders:list"))

        self.assertEqual(list(response.context["orders"]), [own_order])
        self.assertEqual(response.context["orders"].paginator.count, 1)

    # Из списка платежей карточка заказа возвращает
    # к тому же списку с сохранёнными фильтрами и страницей.
    def test_manager_order_detail_returns_to_payment_list(self):
        customer = create_test_user()
        manager = create_test_manager()
        order = create_test_order(user=customer)

        self.client.force_login(manager)

        payment_list_url = reverse("payments:manager_payment_list")
        back_url = f"{payment_list_url}?status=pending&page=2"
        detail_url = reverse(
            "orders:manager_order_detail",
            args=[order.pk],
        )

        response = self.client.get(detail_url, {"next": back_url})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], back_url)
