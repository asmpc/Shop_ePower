from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.chat.models import ChatRoomStatus
from shop_epower.chat.tests.helpers import create_test_chat_room


class TestsCustomerChatRoomPagination(TestCase):
    # Клиент видит не больше 20 комнат на одной странице.
    def test_customer_room_list_is_paginated(self):
        user = create_test_user()

        for _ in range(21):
            create_test_chat_room(user=user)

        self.client.force_login(user)
        url = reverse("chat:room_list")

        first_page = self.client.get(url)
        second_page = self.client.get(url, {"page": 2})

        self.assertEqual(len(first_page.context["rooms"]), 20)
        self.assertEqual(len(second_page.context["rooms"]), 1)

    # Пагинация сохраняет выбранный статус CLOSED.
    def test_customer_room_pagination_preserves_closed_filter(self):
        user = create_test_user()

        for _ in range(21):
            create_test_chat_room(
                user=user,
                status=ChatRoomStatus.CLOSED,
            )

        self.client.force_login(user)
        url = reverse("chat:room_list")

        first_page = self.client.get(
            url,
            {"status": "closed"},
        )
        second_page = self.client.get(
            url,
            {"status": "closed", "page": 2},
        )

        self.assertEqual(len(first_page.context["rooms"]), 20)
        self.assertEqual(len(second_page.context["rooms"]), 1)
        self.assertContains(
            first_page,
            'href="?status=closed&amp;page=2"',
        )
        self.assertContains(
            second_page,
            'href="?status=closed&amp;page=1"',
        )

    # Из комнаты клиент возвращается к тому же фильтру и странице.
    def test_back_to_chat_rooms_preserves_closed_filter_and_page(self):
        user = create_test_user()

        for _ in range(21):
            create_test_chat_room(
                user=user,
                status=ChatRoomStatus.CLOSED,
            )

        self.client.force_login(user)
        list_url = reverse("chat:room_list")
        list_response = self.client.get(
            list_url,
            {"status": "closed", "page": 2},
        )

        room = list_response.context["rooms"][0]
        detail_url = reverse("chat:room_detail", args=[room.pk])

        self.assertContains(
            list_response,
            f'href="{detail_url}?status=closed&amp;page=2"',
        )

        detail_response = self.client.get(
            detail_url,
            {"status": "closed", "page": 2},
        )
        self.assertContains(
            detail_response,
            f'href="{list_url}?status=closed&amp;page=2"',
        )


class TestsAdminChatRoomPagination(TestCase):
    # Администратор не загружает все активные комнаты одной страницей.
    def test_admin_room_list_is_paginated(self):
        admin = create_test_user(role="admin")

        for _ in range(21):
            create_test_chat_room()

        self.client.force_login(admin)
        url = reverse("chat:room_list")

        first_page = self.client.get(url)
        second_page = self.client.get(url, {"page": 2})

        self.assertEqual(len(first_page.context["rooms"]), 20)
        self.assertEqual(len(second_page.context["rooms"]), 1)

    # Переход по страницам архива сохраняет фильтр CLOSED.
    def test_admin_room_pagination_preserves_closed_filter(self):
        admin = create_test_user(role="admin")

        for _ in range(21):
            create_test_chat_room(status=ChatRoomStatus.CLOSED)

        create_test_chat_room(status=ChatRoomStatus.OPEN)

        self.client.force_login(admin)
        url = reverse("chat:room_list")

        first_page = self.client.get(url, {"status": "closed"})
        second_page = self.client.get(
            url,
            {"status": "closed", "page": 2},
        )

        self.assertEqual(len(first_page.context["rooms"]), 20)
        self.assertEqual(len(second_page.context["rooms"]), 1)
        self.assertContains(
            first_page,
            'href="?status=closed&amp;page=2"',
        )


class TestsManagerChatRoomPagination(TestCase):
    # Свободные комнаты листаются отдельно от активных комнат менеджера.
    def test_manager_available_rooms_are_paginated_independently(self):
        manager = create_test_manager()

        for _ in range(21):
            create_test_chat_room(status=ChatRoomStatus.OPEN)

        own_active_room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)
        url = reverse("chat:room_list")

        first_page = self.client.get(url)
        second_page = self.client.get(url, {"available_page": 2})

        self.assertEqual(len(first_page.context["available_rooms"]), 20)
        self.assertEqual(len(second_page.context["available_rooms"]), 1)
        self.assertEqual(
            list(first_page.context["active_rooms"]),
            [own_active_room],
        )
        self.assertEqual(
            list(second_page.context["active_rooms"]),
            [own_active_room],
        )

    # Активные комнаты листаются отдельно от свободной очереди.
    def test_manager_active_rooms_are_paginated_independently(self):
        manager = create_test_manager()

        available_room = create_test_chat_room(
            status=ChatRoomStatus.OPEN,
        )

        for _ in range(21):
            create_test_chat_room(
                manager=manager,
                status=ChatRoomStatus.IN_PROGRESS,
            )

        self.client.force_login(manager)
        url = reverse("chat:room_list")

        first_page = self.client.get(url)
        second_page = self.client.get(url, {"active_page": 2})

        self.assertEqual(len(first_page.context["active_rooms"]), 20)
        self.assertEqual(len(second_page.context["active_rooms"]), 1)
        self.assertEqual(
            list(first_page.context["available_rooms"]),
            [available_room],
        )
        self.assertEqual(
            list(second_page.context["available_rooms"]),
            [available_room],
        )

    # Ссылка свободной очереди сохраняет страницу активной очереди.
    def test_available_room_page_link_preserves_active_page(self):
        manager = create_test_manager()

        for _ in range(21):
            create_test_chat_room(status=ChatRoomStatus.OPEN)
            create_test_chat_room(
                manager=manager,
                status=ChatRoomStatus.IN_PROGRESS,
            )

        self.client.force_login(manager)
        response = self.client.get(
            reverse("chat:room_list"),
            {"active_page": 2},
        )

        self.assertContains(
            response,
            'href="?active_page=2&amp;available_page=2"',
        )

    # Ссылка активной очереди сохраняет страницу свободной очереди.
    def test_active_room_page_link_preserves_available_page(self):
        manager = create_test_manager()

        for _ in range(21):
            create_test_chat_room(status=ChatRoomStatus.OPEN)
            create_test_chat_room(
                manager=manager,
                status=ChatRoomStatus.IN_PROGRESS,
            )

        self.client.force_login(manager)
        response = self.client.get(
            reverse("chat:room_list"),
            {"available_page": 2},
        )

        self.assertContains(
            response,
            'href="?available_page=2&amp;active_page=2"',
        )

    # Архив менеджера ограничен 20 комнатами и сохраняет фильтр.
    def test_manager_closed_rooms_are_paginated(self):
        manager = create_test_manager()
        other_manager = create_test_manager()

        for _ in range(21):
            create_test_chat_room(
                manager=manager,
                status=ChatRoomStatus.CLOSED,
            )

        create_test_chat_room(
            manager=other_manager,
            status=ChatRoomStatus.CLOSED,
        )

        self.client.force_login(manager)
        url = reverse("chat:room_list")

        first_page = self.client.get(url, {"status": "closed"})
        second_page = self.client.get(
            url,
            {"status": "closed", "page": 2},
        )

        self.assertEqual(len(first_page.context["rooms"]), 20)
        self.assertEqual(len(second_page.context["rooms"]), 1)
        self.assertContains(
            first_page,
            'href="?status=closed&amp;page=2"',
        )

    # Возврат из комнаты сохраняет страницы обеих очередей.
    def test_manager_back_to_rooms_preserves_both_pages(self):
        manager = create_test_manager()

        for _ in range(21):
            create_test_chat_room(status=ChatRoomStatus.OPEN)
            create_test_chat_room(
                manager=manager,
                status=ChatRoomStatus.IN_PROGRESS,
            )

        self.client.force_login(manager)
        list_url = reverse("chat:room_list")
        query = {"available_page": 2, "active_page": 2}
        list_response = self.client.get(list_url, query)

        room = list_response.context["active_rooms"][0]
        detail_url = reverse("chat:room_detail", args=[room.pk])

        self.assertContains(
            list_response,
            f'href="{detail_url}?available_page=2&amp;active_page=2"',
        )

        detail_response = self.client.get(detail_url, query)
        self.assertContains(
            detail_response,
            f'href="{list_url}?available_page=2&amp;active_page=2"',
        )

    # Отправка сообщения сохраняет контекст обеих очередей.
    def test_sending_message_preserves_manager_list_pages(self):
        manager = create_test_manager()

        for _ in range(21):
            create_test_chat_room(status=ChatRoomStatus.OPEN)
            create_test_chat_room(
                manager=manager,
                status=ChatRoomStatus.IN_PROGRESS,
            )

        self.client.force_login(manager)
        query = {
            "available_page": 2,
            "active_page": 2,
        }
        list_response = self.client.get(
            reverse("chat:room_list"),
            query,
        )
        room = list_response.context["active_rooms"][0]

        detail_url = reverse("chat:room_detail", args=[room.pk])
        send_url = reverse("chat:room_send", args=[room.pk])
        detail_response = self.client.get(detail_url, query)

        self.assertContains(
            detail_response,
            f'action="{send_url}?available_page=2&amp;active_page=2"',
        )

        response = self.client.post(
            f"{send_url}?available_page=2&active_page=2",
            {"text": "Test message"},
        )

        self.assertEqual(room.messages.count(), 1)
        self.assertEqual(
            response["Location"],
            f"{detail_url}?available_page=2&active_page=2",
        )

    # Взятие комнаты сохраняет фильтр и страницу очереди.
    def test_taking_room_preserves_available_list_context(self):
        manager = create_test_manager()

        for _ in range(21):
            create_test_chat_room(status=ChatRoomStatus.OPEN)

        self.client.force_login(manager)
        query = {"status": "open", "available_page": 2}
        list_response = self.client.get(
            reverse("chat:room_list"),
            query,
        )
        room = list_response.context["available_rooms"][0]

        detail_url = reverse("chat:room_detail", args=[room.pk])
        take_url = reverse("chat:room_take", args=[room.pk])
        detail_response = self.client.get(detail_url, query)

        self.assertContains(
            detail_response,
            f'action="{take_url}?status=open&amp;available_page=2">',
        )

        response = self.client.post(
            f"{take_url}?status=open&available_page=2",
        )

        room.refresh_from_db()
        self.assertEqual(room.status, ChatRoomStatus.IN_PROGRESS)
        self.assertEqual(
            response["Location"],
            f"{detail_url}?status=open&available_page=2",
        )

    # Закрытие комнаты сохраняет страницу активной очереди.
    def test_closing_room_preserves_active_list_context(self):
        manager = create_test_manager()

        for _ in range(21):
            create_test_chat_room(
                manager=manager,
                status=ChatRoomStatus.IN_PROGRESS,
            )

        self.client.force_login(manager)
        query = {"status": "in_progress", "active_page": 2}
        list_response = self.client.get(
            reverse("chat:room_list"),
            query,
        )
        room = list_response.context["active_rooms"][0]

        detail_url = reverse("chat:room_detail", args=[room.pk])
        close_url = reverse("chat:room_close", args=[room.pk])
        detail_response = self.client.get(detail_url, query)

        self.assertContains(
            detail_response,
            f'action="{close_url}?status=in_progress&amp;active_page=2"',
        )

        response = self.client.post(
            f"{close_url}?status=in_progress&active_page=2",
        )

        room.refresh_from_db()
        self.assertEqual(room.status, ChatRoomStatus.CLOSED)
        self.assertEqual(
            response["Location"],
            f"{detail_url}?status=in_progress&active_page=2",
        )
