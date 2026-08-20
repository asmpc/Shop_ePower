from django.test import TestCase

from shop_epower.chat.models import ChatRoomStatus
from shop_epower.chat.selectors import (
    get_active_chat_rooms_for_manager,
    get_available_chat_rooms_for_manager,
    get_chat_room_messages,
    get_chat_rooms_for_user,
)
from shop_epower.chat.services import send_chat_message

from .helpers import (
    create_chat_room,
    create_user,
)
from shop_epower.accounts.tests.helpers import create_test_manager



class ChatSelectorsTests(TestCase):

    # Проверяем selector клиентских комнат:
    # пользователь должен видеть только свои комнаты,
    # комнаты других клиентов не попадают в выборку.
    def test_get_chat_rooms_for_user(self):
        user = create_user()
        other_user = create_user(
            username="other-user",
            email="other-user@example.com",
        )

        user_room = create_chat_room(user=user)
        create_chat_room(user=other_user)

        rooms = get_chat_rooms_for_user(user=user)

        self.assertIn(user_room, rooms)
        self.assertEqual(rooms.count(), 1)

    # Проверяем selector свободных комнат:
    # менеджер должен видеть только OPEN комнаты,
    # которые ещё не закреплены за менеджером.
    def test_get_available_chat_rooms_for_manager(self):
        manager = create_test_manager()

        open_room = create_chat_room()
        create_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )
        create_chat_room(
            status=ChatRoomStatus.CLOSED,
        )

        rooms = get_available_chat_rooms_for_manager()

        self.assertIn(open_room, rooms)
        self.assertEqual(rooms.count(), 1)

    # Проверяем selector активных комнат менеджера:
    # менеджер получает только свои IN_PROGRESS комнаты,
    # комнаты других менеджеров не попадают в выборку.
    def test_get_active_chat_rooms_for_manager(self):
        manager = create_test_manager()
        other_manager = create_test_manager(
            username="other-manager",
            email="other-manager@example.com",
        )

        manager_room = create_chat_room(
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )
        create_chat_room(
            manager=other_manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )
        create_chat_room(status=ChatRoomStatus.OPEN)

        rooms = get_active_chat_rooms_for_manager(manager=manager)

        self.assertIn(manager_room, rooms)
        self.assertEqual(rooms.count(), 1)

    # Проверяем selector сообщений комнаты:
    # сообщения выбранной комнаты возвращаются
    # в порядке создания.
    def test_get_chat_room_messages(self):
        user = create_user()
        manager = create_test_manager()

        room = create_chat_room(
            user=user,
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        message_1, _ = send_chat_message(
            room=room,
            sender=user,
            text="First message",
        )
        message_2, _ = send_chat_message(
            room=room,
            sender=manager,
            text="Second message",
        )

        messages = get_chat_room_messages(room=room)

        self.assertEqual(
            list(messages),
            [message_1, message_2],
        )

    # Проверяем unread counter для клиента:
    # клиент видит непрочитанными только сообщения,
    # которые написал не он сам.
    def test_get_chat_rooms_for_user_with_unread_messages_count(self):
        user = create_user()
        manager = create_test_manager()

        room = create_chat_room(
            user=user,
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        send_chat_message(
            room=room,
            sender=manager,
            text="Message from manager",
        )
        send_chat_message(
            room=room,
            sender=user,
            text="Message from client",
        )

        rooms = get_chat_rooms_for_user(user=user)

        self.assertEqual(
            rooms[0].unread_messages_count,
            1,
        )

    # Проверяем unread counter для менеджера:
    # менеджер видит непрочитанными только сообщения клиента,
    # свои сообщения в счётчик не попадают.
    def test_get_active_chat_rooms_for_manager_with_unread_messages_count(self):
        user = create_user()
        manager = create_test_manager()

        room = create_chat_room(
            user=user,
            manager=manager,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        send_chat_message(
            room=room,
            sender=user,
            text="Message from client",
        )
        send_chat_message(
            room=room,
            sender=manager,
            text="Message from manager",
        )

        rooms = get_active_chat_rooms_for_manager(
            manager=manager,
        )

        self.assertEqual(
            rooms[0].unread_messages_count,
            1,
        )