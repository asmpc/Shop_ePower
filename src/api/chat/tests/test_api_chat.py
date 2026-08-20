from django.test import TestCase

from rest_framework.test import APIClient

from shop_epower.chat.models import (
    ChatMessage,
    ChatRoom,
    ChatRoomStatus,
)
from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)



class TestsChatAPI(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.client_user = create_test_user(
            email="client-chat-api@example.com",
            username="client-chat-api",
            password="testpass123",
        )

        self.other_client = create_test_user(
            email="other-client-chat-api@example.com",
            username="other-client-chat-api",
            password="testpass123",
        )

        self.manager = create_test_manager(
            email="manager-chat-api@example.com",
            username="manager-chat-api",
            password="testpass123",
        )

        self.room = ChatRoom.objects.create(
            user=self.client_user,
            status=ChatRoomStatus.OPEN,
        )

        self.other_room = ChatRoom.objects.create(
            user=self.other_client,
            status=ChatRoomStatus.OPEN,
        )

        self.message = ChatMessage.objects.create(
            room=self.room,
            sender=self.client_user,
            text="Hello API",
        )

    # Проверяем chat rooms list API:
    # клиент получает только свои chat rooms,
    # комнаты других клиентов в ответ не попадают.
    def test_client_can_get_own_chat_rooms_list(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.get(
            "/api/chat/rooms/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.room.id)

    # Проверяем permissions chat rooms list API:
    # менеджер может получить список chat rooms,
    # включая открытые обращения клиентов.
    def test_manager_can_get_chat_rooms_list(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            "/api/chat/rooms/",
        )

        self.assertEqual(response.status_code, 200)

        room_ids = [
            room["id"] for room in response.data
        ]

        self.assertIn(self.room.id, room_ids)
        self.assertIn(self.other_room.id, room_ids)

    # Проверяем chat room detail API:
    # клиент может получить detail только своей комнаты.
    def test_client_can_get_own_chat_room_detail(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.get(
            f"/api/chat/rooms/{self.room.id}/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.room.id)
        self.assertEqual(response.data["status"], ChatRoomStatus.OPEN)

    # Проверяем permissions chat room detail API:
    # клиент не может получить detail комнаты другого клиента.
    def test_client_cannot_get_other_client_room_detail(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.get(
            f"/api/chat/rooms/{self.other_room.id}/",
        )

        self.assertEqual(response.status_code, 404)

    # Проверяем chat messages API:
    # пользователь может получить список сообщений
    # доступной ему chat room.
    def test_client_can_get_room_messages(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.get(
            f"/api/chat/rooms/{self.room.id}/messages/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["text"], "Hello API")

    # Проверяем take room API:
    # менеджер может взять OPEN комнату,
    # после этого комната становится IN_PROGRESS.
    def test_manager_can_take_open_room(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f"/api/chat/rooms/{self.room.id}/take/",
        )

        self.assertEqual(response.status_code, 200)

        self.room.refresh_from_db()

        self.assertEqual(self.room.manager, self.manager)
        self.assertEqual(
            self.room.status,
            ChatRoomStatus.IN_PROGRESS,
        )

    # Проверяем permissions take room API:
    # обычный клиент не может взять комнату в работу.
    def test_client_cannot_take_room(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.post(
            f"/api/chat/rooms/{self.room.id}/take/",
        )

        self.assertEqual(response.status_code, 403)

    # Проверяем send message API:
    # клиент может отправить сообщение
    # в свою chat room.
    def test_client_can_send_message_to_own_room(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.post(
            f"/api/chat/rooms/{self.room.id}/send/",
            {
                "text": "Message from API",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            ChatMessage.objects.filter(
                room=self.room,
                sender=self.client_user,
                text="Message from API",
            ).exists()
        )

    # Проверяем permissions send message API:
    # клиент не может отправить сообщение
    # в комнату другого клиента.
    def test_client_cannot_send_message_to_other_client_room(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.post(
            f"/api/chat/rooms/{self.other_room.id}/send/",
            {
                "text": "Forbidden message",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    # Проверяем close room API:
    # клиент может закрыть свою chat room.
    def test_client_can_close_own_room(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.post(
            f"/api/chat/rooms/{self.room.id}/close/",
        )

        self.assertEqual(response.status_code, 200)

        self.room.refresh_from_db()

        self.assertEqual(
            self.room.status,
            ChatRoomStatus.CLOSED,
        )
        self.assertIsNotNone(self.room.closed_at)

    # Проверяем close room API:
    # менеджер может закрыть комнату,
    # если она закреплена за ним.
    def test_manager_can_close_own_active_room(self):
        self.room.manager = self.manager
        self.room.status = ChatRoomStatus.IN_PROGRESS
        self.room.save(
            update_fields=[
                "manager",
                "status",
            ]
        )

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f"/api/chat/rooms/{self.room.id}/close/",
        )

        self.assertEqual(response.status_code, 200)

        self.room.refresh_from_db()

        self.assertEqual(
            self.room.status,
            ChatRoomStatus.CLOSED,
        )

    # Проверяем permissions close room API:
    # менеджер не может закрыть комнату,
    # которая за ним не закреплена.
    def test_manager_cannot_close_not_assigned_room(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f"/api/chat/rooms/{self.room.id}/close/",
        )

        self.assertEqual(response.status_code, 403)