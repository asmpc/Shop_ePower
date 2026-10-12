from django.test import Client, TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.chat.models import ChatRoom, ChatRoomStatus
from shop_epower.chat.services import (
    send_chat_message,
    take_chat_room,
)
from shop_epower.chat.tests.helpers import (
    create_test_chat_room,
)
from shop_epower.orders.tests.helpers import create_test_order


class TestsChatView(TestCase):
    # Проверяем доступ к списку chat rooms:
    # анонимный пользователь не может открыть страницу,
    # Django перенаправляет его на login.
    def test_anonymous_user_cannot_access_room_list(self):
        url = reverse("chat:room_list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)

    # Проверяем доступ к списку chat rooms:
    # авторизованный пользователь может открыть страницу,
    # view возвращает успешный HTTP 200.
    def test_authorized_user_can_access_room_list(self):
        user = create_test_user()
        self.client.force_login(user)

        url = reverse("chat:room_list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    # Проверяем доступ к деталям chat room:
    # анонимный пользователь не может открыть комнату,
    # Django перенаправляет его на login.
    def test_anonymous_user_cannot_access_room_detail(self):
        room = create_test_chat_room()
        url = reverse(
            "chat:room_detail",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)

    # Проверяем доступ к деталям chat room:
    # авторизованный пользователь может открыть комнату,
    # view возвращает успешный HTTP 200.
    def test_authorized_user_can_access_room_detail(self):
        user = create_test_user()
        room = create_test_chat_room(user=user)
        self.client.force_login(user)

        url = reverse(
            "chat:room_detail",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    # Проверяем room list для клиента:
    # клиент видит свою chat room,
    # но не видит комнаты других клиентов.
    def test_client_room_list_shows_only_own_rooms(self):
        user = create_test_user()
        other_user = create_test_user()

        user_room = create_test_chat_room(user=user)
        other_room = create_test_chat_room(user=other_user)

        self.client.force_login(user)

        url = reverse("chat:room_list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(user_room, response.context["rooms"])
        self.assertNotIn(other_room, response.context["rooms"])

    # Проверяем room list для менеджера:
    # менеджер видит свободные OPEN комнаты
    # и свои активные IN_PROGRESS комнаты.
    def test_manager_room_list_shows_available_and_active_rooms(self):
        manager = create_test_manager()
        other_manager = create_test_manager()

        open_room = create_test_chat_room()
        manager_room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )
        other_manager_room = create_test_chat_room(
            manager=other_manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )
        closed_room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.CLOSED,
        )

        self.client.force_login(manager)

        url = reverse("chat:room_list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(open_room, response.context["available_rooms"])
        self.assertIn(manager_room, response.context["active_rooms"])
        self.assertNotIn(other_manager_room, response.context["active_rooms"])
        self.assertNotIn(closed_room, response.context["available_rooms"])
        self.assertNotIn(closed_room, response.context["active_rooms"])
        self.assertEqual(list(response.context["rooms"]), [])
        self.assertNotContains(response, f"Room #{closed_room.pk}")

    # Проверяем room detail для клиента:
    # клиент может открыть свою chat room,
    # view возвращает сообщения комнаты.
    def test_client_can_access_own_room_detail(self):
        user = create_test_user()
        room = create_test_chat_room(user=user)

        self.client.force_login(user)

        url = reverse(
            "chat:room_detail",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["room"], room)

    # Проверяем защиту room detail для клиента:
    # клиент не может открыть chat room,
    # которая принадлежит другому пользователю.
    def test_client_cannot_access_other_user_room_detail(self):
        user = create_test_user()
        other_user = create_test_user()

        other_room = create_test_chat_room(user=other_user)

        self.client.force_login(user)

        url = reverse(
            "chat:room_detail",
            kwargs={
                "pk": other_room.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    # Проверяем room detail для менеджера:
    # менеджер может открыть IN_PROGRESS комнату,
    # если она закреплена именно за ним.
    def test_manager_can_access_own_active_room_detail(self):
        manager = create_test_manager()

        room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)

        url = reverse(
            "chat:room_detail",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["room"], room)

    # Проверяем защиту room detail для менеджера:
    # менеджер не может открыть IN_PROGRESS комнату,
    # которая закреплена за другим менеджером.
    def test_manager_cannot_access_other_manager_active_room_detail(self):
        manager = create_test_manager()
        other_manager = create_test_manager()

        other_room = create_test_chat_room(
            manager=other_manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)

        url = reverse(
            "chat:room_detail",
            kwargs={
                "pk": other_room.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    # Проверяем manager workflow:
    # менеджер может взять свободную OPEN комнату,
    # после чего комната становится IN_PROGRESS.
    def test_manager_can_take_open_room(self):
        manager = create_test_manager()

        room = create_test_chat_room(
            status=ChatRoomStatus.OPEN,
        )

        self.client.force_login(manager)

        url = reverse(
            "chat:room_take",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(url)

        room.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(room.manager, manager)
        self.assertEqual(
            room.status,
            ChatRoomStatus.IN_PROGRESS,
        )

    # Проверяем отправку формы «Take room» с настоящей CSRF-проверкой.
    def test_manager_can_take_open_room_with_csrf(self):
        manager = create_test_manager()
        room = create_test_chat_room(status=ChatRoomStatus.OPEN)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(manager)

        detail_url = reverse("chat:room_detail", args=[room.pk])
        take_url = reverse("chat:room_take", args=[room.pk])

        page = browser.get(f"{detail_url}?status=active")
        html = page.content.decode()

        form_start = f'action="{take_url}?status=active">'
        self.assertIn(form_start, html)

        take_form = html.split(form_start, 1)[1].split("</form>", 1)[0]
        token_start = 'name="csrfmiddlewaretoken" value="'
        self.assertIn(token_start, take_form)
        token = take_form.split(token_start, 1)[1].split('"', 1)[0]

        response = browser.post(
            f"{take_url}?status=active",
            {"csrfmiddlewaretoken": token},
        )

        self.assertEqual(response.status_code, 302)
        room.refresh_from_db()
        self.assertEqual(room.status, ChatRoomStatus.IN_PROGRESS)

    # Проверяем права room_take:
    # клиент не может брать chat room,
    # действие доступно только менеджерам.
    def test_client_cannot_take_room(self):
        user = create_test_user()

        room = create_test_chat_room()

        self.client.force_login(user)

        url = reverse(
            "chat:room_take",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    # Проверяем защиту manager workflow:
    # если комната уже находится в IN_PROGRESS,
    # другой менеджер не может взять её повторно.
    def test_manager_cannot_take_in_progress_room(self):
        manager_1 = create_test_manager(
            username="manager-1",
            email="manager-1@example.com",
        )

        manager_2 = create_test_manager(
            username="manager-2",
            email="manager-2@example.com",
        )

        room = create_test_chat_room(
            manager=manager_1,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager_2)

        url = reverse(
            "chat:room_take",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    # Проверяем close room workflow:
    # менеджер может закрыть свою IN_PROGRESS комнату,
    # статус меняется на CLOSED и заполняется closed_at.
    def test_manager_can_close_own_room(self):
        manager = create_test_manager()

        room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)

        url = reverse(
            "chat:room_close",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(url)

        room.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(room.status, ChatRoomStatus.CLOSED)
        self.assertIsNotNone(room.closed_at)

    # Проверяем защиту close room:
    # менеджер не может закрыть комнату,
    # которая закреплена за другим менеджером.
    def test_manager_cannot_close_other_manager_room(self):
        manager = create_test_manager()
        other_manager = create_test_manager()

        room = create_test_chat_room(
            manager=other_manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)

        url = reverse(
            "chat:room_close",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    # Проверяем защиту повторного закрытия:
    # если комната уже CLOSED,
    # повторное закрытие через view запрещено.
    def test_closed_room_cannot_be_closed_again(self):
        manager = create_test_manager()

        room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.CLOSED,
        )

        self.client.force_login(manager)

        url = reverse(
            "chat:room_close",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    # Проверяем отправку сообщения клиентом:
    # клиент может отправить сообщение
    # в свою OPEN chat room.
    def test_client_can_send_message_to_own_room(self):
        user = create_test_user()
        room = create_test_chat_room(user=user)

        self.client.force_login(user)

        url = reverse(
            "chat:room_send",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "text": "Hello from client",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(room.messages.count(), 1)
        self.assertEqual(
            room.messages.first().text,
            "Hello from client",
        )

    # Проверяем отправку сообщения менеджером:
    # менеджер может отправить сообщение
    # в свою IN_PROGRESS chat room.
    def test_manager_can_send_message_to_own_active_room(self):
        manager = create_test_manager()

        room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)

        url = reverse(
            "chat:room_send",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "text": "Hello from manager",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(room.messages.count(), 1)
        self.assertEqual(
            room.messages.first().text,
            "Hello from manager",
        )

    # Проверяем защиту отправки сообщения:
    # клиент не может отправить сообщение
    # в chat room другого клиента.
    def test_client_cannot_send_message_to_other_user_room(self):
        user = create_test_user()
        other_user = create_test_user()

        other_room = create_test_chat_room(user=other_user)

        self.client.force_login(user)

        url = reverse(
            "chat:room_send",
            kwargs={
                "pk": other_room.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "text": "Forbidden message",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(other_room.messages.count(), 0)

    # Проверяем защиту закрытой комнаты:
    # пользователь не может отправить сообщение
    # в CLOSED chat room.
    def test_user_cannot_send_message_to_closed_room(self):
        user = create_test_user()

        room = create_test_chat_room(
            user=user,
            status=ChatRoomStatus.CLOSED,
        )

        self.client.force_login(user)

        url = reverse(
            "chat:room_send",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.post(
            url,
            data={
                "text": "Message to closed room",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(room.messages.count(), 0)

    # Проверяем создание chat room:
    # клиент может создать новую комнату,
    # после создания статус комнаты OPEN.
    def test_client_can_create_chat_room(self):
        user = create_test_user()

        self.client.force_login(user)

        url = reverse("chat:room_create")

        response = self.client.post(url)

        room = ChatRoom.objects.get(user=user)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(room.status, ChatRoomStatus.OPEN)
        self.assertIsNone(room.manager)

    # Проверяем создание chat room с заказом:
    # клиент может создать обращение,
    # связанное со своим заказом.
    def test_client_can_create_chat_room_with_order(self):
        user = create_test_user()
        order = create_test_order(
            user=user,
        )

        self.client.force_login(user)

        url = reverse("chat:room_create")

        response = self.client.post(
            url,
            data={
                "order": order.pk,
            },
        )

        room = ChatRoom.objects.get(user=user)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(room.order, order)

    # Проверяем права создания chat room:
    # менеджер не может создавать клиентские обращения,
    # это действие доступно только клиенту.
    def test_manager_cannot_create_chat_room(self):
        manager = create_test_manager()

        self.client.force_login(manager)

        url = reverse("chat:room_create")

        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    # manager может открыть OPEN комнату, но писать нельзя, пока не взял
    def test_manager_can_view_open_room_but_cannot_send(self):
        manager = create_test_manager()
        room = create_test_chat_room(status=ChatRoomStatus.OPEN)

        self.client.force_login(manager)
        url = reverse("chat:room_detail", kwargs={"pk": room.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # форма отправки сообщений должна быть скрыта
        self.assertNotContains(
            response,
            '<form method="post" action="{% url \'chat:room_send\' room.pk %}"',
        )

    # manager берет комнату через room_detail -> кнопка Take
    def test_manager_can_take_room_in_detail(self):
        manager = create_test_manager()
        room = create_test_chat_room(status=ChatRoomStatus.OPEN)

        self.client.force_login(manager)

        # имитируем POST на Take
        take_url = reverse("chat:room_take", kwargs={"pk": room.pk})
        response = self.client.post(take_url)

        self.assertEqual(response.status_code, 302)

        room.refresh_from_db()

        self.assertEqual(room.status, ChatRoomStatus.IN_PROGRESS)
        self.assertEqual(room.manager, manager)

    # после Take manager может писать
    def test_manager_can_send_after_take(self):
        manager = create_test_manager()
        room = create_test_chat_room(status=ChatRoomStatus.OPEN)

        # взять комнату
        take_chat_room(room=room, manager=manager)

        self.client.force_login(manager)
        send_url = reverse("chat:room_send", kwargs={"pk": room.pk})
        response = self.client.post(
            send_url,
            data={"text": "Hello"},
        )

        self.assertEqual(response.status_code, 302)

        room.refresh_from_db()

        self.assertEqual(room.messages.count(), 1)
        self.assertEqual(room.messages.first().text, "Hello")

    # Проверяем auto mark as read:
    # когда пользователь открывает room detail,
    # сообщения собеседника помечаются прочитанными.
    def test_room_detail_marks_messages_as_read(self):
        user = create_test_user()
        manager = create_test_manager()

        room = create_test_chat_room(
            user=user,
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        message_from_manager, _ = send_chat_message(
            room=room,
            sender=manager,
            text="Message from manager",
        )

        message_from_user, _ = send_chat_message(
            room=room,
            sender=user,
            text="Message from user",
        )

        self.client.force_login(user)

        url = reverse(
            "chat:room_detail",
            kwargs={
                "pk": room.pk,
            },
        )

        response = self.client.get(url)

        message_from_manager.refresh_from_db()
        message_from_user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(message_from_manager.is_read)
        self.assertFalse(message_from_user.is_read)

    # Проверяем room list для администратора:
    # admin видит все chat rooms,
    # независимо от клиента, менеджера и статуса.
    def test_admin_room_list_shows_all_rooms(self):
        admin = create_test_user(
            username="admin",
            email="admin@example.com",
            role="admin",
        )

        user = create_test_user()

        room = create_test_chat_room(
            user=user,
            status=ChatRoomStatus.OPEN,
        )

        self.client.force_login(admin)

        url = reverse("chat:room_list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(room, response.context["rooms"])

    # Администратор без фильтра видит рабочие комнаты, но не архив.
    def test_admin_room_list_shows_only_active_rooms_by_default(self):
        admin = create_test_user(role="admin")
        manager = create_test_manager()

        open_room = create_test_chat_room(status=ChatRoomStatus.OPEN)
        active_room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )
        create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.CLOSED,
        )

        self.client.force_login(admin)
        response = self.client.get(reverse("chat:room_list"))

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            response.context["rooms"],
            [open_room, active_room],
        )

    # Форма администратора показывает активный список по умолчанию.
    def test_admin_room_filter_defaults_to_active(self):
        admin = create_test_user(role="admin")
        self.client.force_login(admin)

        response = self.client.get(reverse("chat:room_list"))

        self.assertContains(
            response,
            '<option value="active" selected>Active</option>',
        )
        self.assertNotContains(response, '<option value="all"')

    # Клиент без фильтра видит только свои незакрытые комнаты.
    def test_client_room_list_shows_only_active_rooms_by_default(self):
        user = create_test_user()

        open_room = create_test_chat_room(
            user=user,
            status=ChatRoomStatus.OPEN,
        )
        active_room = create_test_chat_room(
            user=user,
            status=ChatRoomStatus.IN_PROGRESS,
        )
        create_test_chat_room(
            user=user,
            status=ChatRoomStatus.CLOSED,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("chat:room_list"))

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            response.context["rooms"],
            [open_room, active_room],
        )

    # Форма клиента показывает активный список по умолчанию.
    def test_client_room_filter_defaults_to_active(self):
        user = create_test_user()
        self.client.force_login(user)

        response = self.client.get(reverse("chat:room_list"))

        self.assertContains(
            response,
            '<option value="active" selected>Active</option>',
        )
        self.assertNotContains(response, '<option value="all"')

    # Фильтр OPEN скрывает комнаты IN_PROGRESS менеджера.
    def test_manager_open_filter_shows_only_available_rooms(self):
        manager = create_test_manager()

        open_room = create_test_chat_room(status=ChatRoomStatus.OPEN)
        create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)
        response = self.client.get(
            reverse("chat:room_list"),
            {"status": ChatRoomStatus.OPEN},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["available_rooms"]),
            [open_room],
        )
        self.assertEqual(
            list(response.context["active_rooms"]),
            [],
        )

    # Фильтр IN_PROGRESS скрывает свободные OPEN-комнаты.
    def test_manager_in_progress_filter_shows_only_own_active_rooms(self):
        manager = create_test_manager()
        other_manager = create_test_manager()

        create_test_chat_room(status=ChatRoomStatus.OPEN)
        own_room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )
        create_test_chat_room(
            manager=other_manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)
        response = self.client.get(
            reverse("chat:room_list"),
            {"status": ChatRoomStatus.IN_PROGRESS},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["available_rooms"]),
            [],
        )
        self.assertEqual(
            list(response.context["active_rooms"]),
            [own_room],
        )

    # Фильтр CLOSED показывает менеджеру только его архив.
    def test_manager_closed_filter_shows_only_own_rooms(self):
        manager = create_test_manager()
        other_manager = create_test_manager()

        own_closed_room = create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.CLOSED,
        )
        other_closed_room = create_test_chat_room(
            manager=other_manager,
            status=ChatRoomStatus.CLOSED,
        )
        create_test_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        self.client.force_login(manager)
        response = self.client.get(
            reverse("chat:room_list"),
            {"status": ChatRoomStatus.CLOSED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["available_rooms"]),
            [],
        )
        self.assertEqual(
            list(response.context["active_rooms"]),
            [],
        )
        self.assertEqual(
            list(response.context["rooms"]),
            [own_closed_room],
        )
        self.assertContains(
            response,
            f"Room #{own_closed_room.pk}",
        )
        self.assertNotContains(
            response,
            f"Room #{other_closed_room.pk}",
        )

    # Прямая ссылка не даёт менеджеру доступ к чужому архиву.
    def test_manager_cannot_access_other_manager_closed_room(self):
        manager = create_test_manager()
        other_manager = create_test_manager()

        other_room = create_test_chat_room(
            manager=other_manager,
            status=ChatRoomStatus.CLOSED,
        )

        self.client.force_login(manager)
        response = self.client.get(
            reverse(
                "chat:room_detail",
                kwargs={"pk": other_room.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    # Клиент открывает только свой архив через явный фильтр.
    def test_client_closed_filter_shows_only_own_rooms(self):
        user = create_test_user()
        other_user = create_test_user()

        own_closed_room = create_test_chat_room(
            user=user,
            status=ChatRoomStatus.CLOSED,
        )
        create_test_chat_room(
            user=other_user,
            status=ChatRoomStatus.CLOSED,
        )
        create_test_chat_room(
            user=user,
            status=ChatRoomStatus.OPEN,
        )

        self.client.force_login(user)
        response = self.client.get(
            reverse("chat:room_list"),
            {"status": ChatRoomStatus.CLOSED},
        )

        self.assertEqual(
            list(response.context["rooms"]),
            [own_closed_room],
        )

    # Администратор видит общий архив только при выборе CLOSED.
    def test_admin_closed_filter_shows_closed_rooms(self):
        admin = create_test_user(role="admin")
        first_user = create_test_user()
        second_user = create_test_user()

        first_closed_room = create_test_chat_room(
            user=first_user,
            status=ChatRoomStatus.CLOSED,
        )
        second_closed_room = create_test_chat_room(
            user=second_user,
            status=ChatRoomStatus.CLOSED,
        )
        create_test_chat_room(
            user=first_user,
            status=ChatRoomStatus.OPEN,
        )

        self.client.force_login(admin)
        response = self.client.get(
            reverse("chat:room_list"),
            {"status": ChatRoomStatus.CLOSED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            response.context["rooms"],
            [first_closed_room, second_closed_room],
        )

    # Админ, действующий как клиент, может закрыть свой новый чат,
    # даже если предыдущий чат по этому заказу уже закрыт.
    def test_admin_can_close_own_second_room_for_same_order(self):
        admin = create_test_admin()
        order = create_test_order(user=admin)

        create_test_chat_room(
            user=admin,
            order=order,
            status=ChatRoomStatus.CLOSED,
        )
        new_room = create_test_chat_room(
            user=admin,
            order=order,
            status=ChatRoomStatus.OPEN,
        )

        self.client.force_login(admin)
        response = self.client.post(
            reverse("chat:room_close", args=[new_room.pk]),
        )

        self.assertEqual(response.status_code, 302)
        new_room.refresh_from_db()
        self.assertEqual(new_room.status, ChatRoomStatus.CLOSED)
