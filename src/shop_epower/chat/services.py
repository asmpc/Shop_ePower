from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import ChatAttachment, ChatMessage, ChatRoom, ChatRoomStatus


def create_chat_room(user, order=None):
    """
    Создаём новую чат-комнату для пользователя.
    По умолчанию статус OPEN.
    """
    return ChatRoom.objects.create(user=user, order=order, status=ChatRoomStatus.OPEN)


def take_chat_room(room: ChatRoom, manager):
    """
    Менеджер берёт свободную комнату (OPEN → IN_PROGRESS).
    Если комната уже занята или закрыта — ValueError.
    """
    if room.status != ChatRoomStatus.OPEN:
        raise ValueError("Room is already taken or closed")

    if manager.role not in ["manager", "admin"]:
        raise PermissionError(
            "Only managers or admins can take a chat room."
        )

    room.manager = manager
    room.status = ChatRoomStatus.IN_PROGRESS
    room.save(update_fields=["manager", "status", "updated_at"])


def close_chat_room(room: ChatRoom, manager):
    """
    Менеджер закрывает свою комнату (IN_PROGRESS → CLOSED)
    """
    if room.manager != manager:
        raise PermissionError("Only assigned manager can close the room")
    room.status = ChatRoomStatus.CLOSED
    room.closed_at = timezone.now()
    room.save(update_fields=["status", "closed_at", "updated_at"])


def send_chat_message(room, sender, text, files=None):
    """
    Создаём сообщение в чат-комнате.

    Клиент может писать только в свои OPEN/IN_PROGRESS комнаты.
    Менеджер может писать только в закреплённую за ним IN_PROGRESS комнату.
    В CLOSED комнату писать нельзя.
    """
    if room.status == ChatRoomStatus.CLOSED:
        raise PermissionDenied("Cannot send message to closed room")

    if sender.role == "client":
        if room.user != sender:
            raise PermissionDenied("Client cannot write in this room")

    elif sender.role == "manager":
        if room.status == ChatRoomStatus.OPEN:
            if room.manager not in (None, sender):
                raise PermissionDenied("Room is taken by another manager")

        if room.status == ChatRoomStatus.IN_PROGRESS:
            if room.manager != sender:
                raise PermissionDenied("Only assigned manager can write in this room")

    with transaction.atomic():
        message = ChatMessage.objects.create(
            room=room,
            sender=sender,
            text=text,
        )

        attachments = []

        if files:
            for file in files:
                attachments.append(
                    ChatAttachment.objects.create(
                        message=message,
                        file=file,
                        original_name=file.name,
                    )
                )

    return message, attachments

def mark_messages_as_read(room, user):
    """
    Помечаем сообщения собеседника в комнате как прочитанные.

    Свои сообщения пользователь не помечает, потому что для него они
    уже считаются отправленными.
    """
    ChatMessage.objects.filter(
        room=room,
        is_read=False,
    ).exclude(
        sender=user,
    ).update(
        is_read=True,
    )

def close_chat_room_by_client(room, user):
    """
    Клиент закрывает свою chat room.

    Закрывать можно только свою комнату.
    CLOSED комнату повторно закрывать нельзя.
    """
    if room.user != user:
        raise PermissionError("Client can close only own room")

    if room.status == ChatRoomStatus.CLOSED:
        raise ValueError("Room is already closed")

    room.status = ChatRoomStatus.CLOSED
    room.closed_at = timezone.now()

    room.save(
        update_fields=[
            "status",
            "closed_at",
            "updated_at",
        ]
    )