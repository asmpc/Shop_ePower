from django.test import TestCase

from shop_epower.chat.models import ChatRoomStatus
from shop_epower.chat.services import (
    close_chat_room,
    close_chat_room_by_client,
    create_chat_room,
    take_chat_room,
)

from .helpers import (
    create_chat_room as helper_create_chat_room,

    create_order,
    create_user,
)
from shop_epower.accounts.tests.helpers import create_test_manager



class TestsChatRoomService(TestCase):

    # Проверяем создание chat room:
    # новая комната создаётся для клиента,
    # статус по умолчанию OPEN, менеджер не назначен.
    def test_create_chat_room(self):
        user = create_user()

        room = create_chat_room(user=user)

        self.assertEqual(room.user, user)
        self.assertIsNone(room.manager)
        self.assertEqual(room.status, ChatRoomStatus.OPEN)

    # Проверяем создание chat room с заказом:
    # если в сервис передан order,
    # комната должна быть связана с этим заказом.
    def test_create_chat_room_with_order(self):
        user = create_user()
        order = create_order(user=user)

        room = create_chat_room(
            user=user,
            order=order,
        )

        self.assertEqual(room.order, order)

    # Проверяем manager workflow:
    # менеджер может взять свободную OPEN комнату,
    # после этого комната переходит в IN_PROGRESS.
    def test_manager_can_take_open_room(self):
        room = helper_create_chat_room()
        manager = create_test_manager()

        take_chat_room(room, manager)

        room.refresh_from_db()

        self.assertEqual(room.manager, manager)
        self.assertEqual(room.status, ChatRoomStatus.IN_PROGRESS)

    # Проверяем защиту manager workflow:
    # если комната уже взята другим менеджером,
    # повторно взять её нельзя.
    def test_cannot_take_room_that_is_already_in_progress(self):
        room = helper_create_chat_room()

        manager_1 = create_test_manager(
            username="manager-1",
            email="manager-1@example.com",
        )
        manager_2 = create_test_manager(
            username="manager-2",
            email="manager-2@example.com",
        )

        take_chat_room(room, manager_1)

        with self.assertRaises(ValueError):
            take_chat_room(room, manager_2)

    # Проверяем закрытие chat room:
    # назначенный менеджер может закрыть свою комнату,
    # статус меняется на CLOSED и заполняется closed_at.
    def test_manager_can_close_room(self):
        room = helper_create_chat_room()
        manager = create_test_manager()

        take_chat_room(room, manager)
        close_chat_room(room, manager)

        room.refresh_from_db()

        self.assertEqual(room.status, ChatRoomStatus.CLOSED)
        self.assertIsNotNone(room.closed_at)

    # Проверяем права закрытия chat room:
    # другой менеджер не может закрыть комнату,
    # которая закреплена не за ним.
    def test_other_manager_cannot_close_room(self):
        room = helper_create_chat_room()

        manager_1 = create_test_manager(
            username="manager-1",
            email="manager-1@example.com",
        )
        manager_2 = create_test_manager(
            username="manager-2",
            email="manager-2@example.com",
        )

        take_chat_room(room, manager_1)

        with self.assertRaises(PermissionError):
            close_chat_room(room, manager_2)

    # Проверяем закрытие chat room клиентом:
    # клиент может закрыть свою комнату,
    # статус меняется на CLOSED и заполняется closed_at.
    def test_client_can_close_own_room(self):
        user = create_user()

        room = helper_create_chat_room(
            user=user,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        close_chat_room_by_client(
            room=room,
            user=user,
        )

        room.refresh_from_db()

        self.assertEqual(room.status, ChatRoomStatus.CLOSED)
        self.assertIsNotNone(room.closed_at)

    # Проверяем защиту закрытия chat room клиентом:
    # клиент не может закрыть комнату,
    # которая принадлежит другому пользователю.
    def test_client_cannot_close_other_user_room(self):
        user = create_user()
        other_user = create_user()

        room = helper_create_chat_room(
            user=other_user,
            status=ChatRoomStatus.IN_PROGRESS,
        )

        with self.assertRaises(PermissionError):
            close_chat_room_by_client(
                room=room,
                user=user,
            )