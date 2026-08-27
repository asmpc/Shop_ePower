from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_manager
from shop_epower.chat.services import (
    mark_messages_as_read,
    send_chat_message,
)
from shop_epower.chat.tests.helpers import (
    create_chat_room,
    create_user,
)


class TestsChatMessageService(TestCase):

    # Проверяем отправку сообщения клиентом:
    # клиент может отправить сообщение
    # только в свою OPEN chat room.
    def test_client_can_send_message_to_own_open_room(self):
        user = create_user()
        room = create_chat_room(user=user)

        message, attachments = send_chat_message(
            room=room,
            sender=user,
            text="Hello",
        )

        self.assertEqual(message.text, "Hello")
        self.assertEqual(message.sender, user)
        self.assertEqual(len(attachments), 0)

    # Проверяем защиту закрытой комнаты:
    # клиент не может отправить сообщение,
    # если chat room уже находится в статусе CLOSED.
    def test_client_cannot_send_message_to_closed_room(self):
        user = create_user()
        room = create_chat_room(
            user=user,
            status="closed",
        )

        with self.assertRaises(PermissionDenied):
            send_chat_message(
                room=room,
                sender=user,
                text="Hello",
            )

    # Проверяем отправку сообщения менеджером:
    # менеджер может писать в IN_PROGRESS комнату,
    # если она закреплена именно за ним.
    def test_manager_can_send_message_to_in_progress_room(self):
        user = create_user()
        manager = create_test_manager()

        room = create_chat_room(
            user=user,
            manager=manager,
            status="in_progress",
        )

        message, attachments = send_chat_message(
            room=room,
            sender=manager,
            text="Manager here",
        )

        self.assertEqual(message.sender, manager)
        self.assertEqual(len(attachments), 0)

    # Проверяем отправку сообщения с файлом:
    # если передан файл,
    # сервис создаёт ChatAttachment с original_name.
    def test_client_message_with_attachments(self):
        user = create_user()
        room = create_chat_room(user=user)

        uploaded_file = SimpleUploadedFile(
            "test.txt",
            b"Hello World",
        )

        message, attachments = send_chat_message(
            room=room,
            sender=user,
            text="See file",
            files=[uploaded_file],
        )

        self.assertEqual(message.sender, user)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].original_name, "test.txt")

    # Проверяем защиту manager workflow:
    # менеджер не может писать в IN_PROGRESS комнату,
    # если она закреплена за другим менеджером.
    def test_manager_cannot_send_message_to_room_taken_by_other(self):
        user = create_user()

        manager_1 = create_test_manager(
            username="manager-1",
            email="manager-1@example.com",
        )
        manager_2 = create_test_manager(
            username="manager-2",
            email="manager-2@example.com",
        )

        room = create_chat_room(
            user=user,
            manager=manager_1,
            status="in_progress",
        )

        with self.assertRaises(PermissionDenied):
            send_chat_message(
                room=room,
                sender=manager_2,
                text="Hello",
            )

    # Проверяем mark as read:
    # пользователь помечает прочитанными сообщения собеседника,
    # но собственные сообщения остаются без изменений.
    def test_mark_messages_as_read(self):
        user = create_user()
        manager = create_test_manager()

        room = create_chat_room(
            user=user,
            manager=manager,
            status="in_progress",
        )

        message_1, _ = send_chat_message(
            room=room,
            sender=manager,
            text="Message 1",
        )
        message_2, _ = send_chat_message(
            room=room,
            sender=manager,
            text="Message 2",
        )
        message_3, _ = send_chat_message(
            room=room,
            sender=user,
            text="Message 3",
        )

        mark_messages_as_read(
            room=room,
            user=user,
        )

        message_1.refresh_from_db()
        message_2.refresh_from_db()
        message_3.refresh_from_db()

        self.assertTrue(message_1.is_read)
        self.assertTrue(message_2.is_read)
        self.assertFalse(message_3.is_read)

    # Проверяем область действия mark as read:
    # сервис помечает сообщения только в выбранной комнате,
    # сообщения из другой комнаты остаются непрочитанными.
    def test_mark_messages_as_read_only_in_selected_room(self):
        user = create_user()
        manager = create_test_manager()

        room_1 = create_chat_room(
            user=user,
            manager=manager,
            status="in_progress",
        )
        room_2 = create_chat_room(
            user=user,
            manager=manager,
            status="in_progress",
        )

        room_1_message, _ = send_chat_message(
            room=room_1,
            sender=manager,
            text="Room 1 message",
        )
        room_2_message, _ = send_chat_message(
            room=room_2,
            sender=manager,
            text="Room 2 message",
        )

        mark_messages_as_read(
            room=room_1,
            user=user,
        )

        room_1_message.refresh_from_db()
        room_2_message.refresh_from_db()

        self.assertTrue(room_1_message.is_read)
        self.assertFalse(room_2_message.is_read)