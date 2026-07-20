from django.contrib.auth import get_user_model
import itertools

from shop_epower.orders.models import Order
from shop_epower.chat.models import (
    ChatAttachment,
    ChatMessage,
    ChatRoom,
    ChatRoomStatus,
)

from shop_epower.accounts.tests.helpers import (
    create_manager,
    create_test_user,
)


create_user = create_test_user



# _user_counter = itertools.count(1)
# _manager_counter = itertools.count(1)


# User = get_user_model()


# def create_user(
#     email=None,
#     username=None,
#     **kwargs,
# ):
#     idx = next(_user_counter)
#
#     return User.objects.create_user(
#         email=email or f"user{idx}@example.com",
#         username=username or f"user{idx}",
#         password="testpass",
#         **kwargs,
#     )


# def create_manager(
#     email=None,
#     username=None,
#     **kwargs,
# ):
#     idx = next(_manager_counter)
#
#     return User.objects.create_user(
#         email=email or f"manager{idx}@example.com",
#         username=username or f"manager{idx}",
#         password="testpass",
#         role="manager",
#         **kwargs,
#     )


def create_order(user=None, **kwargs):
    if user is None:
        user = create_user()
    return Order.objects.create(user=user, total_price=100, **kwargs)


def create_chat_room(
    user=None,
    manager=None,
    order=None,
    status=ChatRoomStatus.OPEN,
):
    if user is None:
        user = create_user()

    return ChatRoom.objects.create(
        user=user,
        manager=manager,
        order=order,
        status=status,
    )


def create_chat_message(room=None, sender=None, text="Test message", is_read=False):
    if room is None:
        room = create_chat_room()
    if sender is None:
        sender = room.user
    return ChatMessage.objects.create(
        room=room,
        sender=sender,
        text=text,
        is_read=is_read,
    )


def create_chat_attachment(message=None, file=None, original_name="file.txt"):
    if message is None:
        message = create_chat_message()
    return ChatAttachment.objects.create(
        message=message,
        file=file,
        original_name=original_name,
    )