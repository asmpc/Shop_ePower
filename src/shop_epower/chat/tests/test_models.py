from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_manager
from shop_epower.chat.models import (
    ChatMessage,
    ChatRoom,
    ChatRoomStatus,
)
from shop_epower.chat.tests.helpers import (
    create_chat_attachment,
    create_chat_message,
    create_chat_room,
    create_user,
)


class TestsChatRoomModel(TestCase):

    # Проверяем модель ChatRoom:
    # новая комната создаётся со статусом OPEN,
    # manager, order и closed_at по умолчанию пустые.
    def test_chat_room_created_with_default_status(self):
        user = create_user()

        room = ChatRoom.objects.create(
            user=user,
        )

        self.assertEqual(room.user, user)
        self.assertIsNone(room.manager)
        self.assertIsNone(room.order)
        self.assertEqual(room.status, ChatRoomStatus.OPEN)
        self.assertIsNone(room.closed_at)

    # Проверяем связь ChatRoom с менеджером:
    # комната может быть закреплена за manager,
    # это нужно для workflow OPEN -> IN_PROGRESS.
    def test_chat_room_can_have_manager(self):
        user = create_user()
        manager = create_test_manager()

        room = create_chat_room(
            user=user,
            manager=manager,
        )

        self.assertEqual(room.manager, manager)

    # Проверяем строковое представление ChatRoom:
    # в админке и debug-выводе должно быть понятно,
    # какая комната отображается и какой у неё статус.
    def test_chat_room_str(self):
        room = create_chat_room()

        self.assertEqual(
            str(room),
            f"Chat room #{room.pk} — {room.status}",
        )


class TestsChatMessageModel(TestCase):

    # Проверяем модель ChatMessage:
    # сообщение создаётся в комнате от конкретного sender,
    # по умолчанию сообщение считается непрочитанным.
    def test_chat_message_created_with_default_is_read_false(self):
        room = create_chat_room()

        message = ChatMessage.objects.create(
            room=room,
            sender=room.user,
            text="Hello",
        )

        self.assertEqual(message.room, room)
        self.assertEqual(message.sender, room.user)
        self.assertEqual(message.text, "Hello")
        self.assertFalse(message.is_read)

    # Проверяем строковое представление ChatMessage:
    # оно должно показывать id сообщения
    # и id комнаты, к которой сообщение относится.
    def test_chat_message_str(self):
        message = create_chat_message()

        self.assertEqual(
            str(message),
            f"Message #{message.pk} in room #{message.room_id}",
        )


class TestsChatAttachmentModel(TestCase):

    # Проверяем модель ChatAttachment:
    # вложение создаётся и связывается с сообщением,
    # original_name хранит имя исходного файла.
    def test_chat_attachment_created(self):
        message = create_chat_message()

        attachment = create_chat_attachment(
            message=message,
            original_name="test.txt",
        )

        self.assertEqual(attachment.message, message)
        self.assertEqual(attachment.original_name, "test.txt")

    # Проверяем строковое представление ChatAttachment:
    # для вложения возвращается original_name,
    # чтобы файл удобно отображался в админке.
    def test_chat_attachment_str(self):
        attachment = create_chat_attachment(
            original_name="document.pdf",
        )

        self.assertEqual(
            str(attachment),
            "document.pdf",
        )