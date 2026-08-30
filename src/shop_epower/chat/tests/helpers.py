from shop_epower.accounts.tests.helpers import (
    create_test_user,
)
from shop_epower.chat.models import (
    ChatAttachment,
    ChatMessage,
    ChatRoom,
    ChatRoomStatus,
)


def create_test_chat_room(
    user=None,
    manager=None,
    order=None,
    status=ChatRoomStatus.OPEN,
):
    if user is None:
        user = create_test_user()

    return ChatRoom.objects.create(
        user=user,
        manager=manager,
        order=order,
        status=status,
    )


def create_test_chat_message(room=None, sender=None, text="Test message", is_read=False):
    if room is None:
        room = create_test_chat_room()
    if sender is None:
        sender = room.user
    return ChatMessage.objects.create(
        room=room,
        sender=sender,
        text=text,
        is_read=is_read,
    )


def create_test_chat_attachment(message=None, file=None, original_name="file.txt"):
    if message is None:
        message = create_test_chat_message()
    return ChatAttachment.objects.create(
        message=message,
        file=file,
        original_name=original_name,
    )