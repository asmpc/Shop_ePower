from django.db.models import Count, OuterRef, Q, Subquery

from shop_epower.chat.models import (
    ChatMessage,
    ChatRoom,
    ChatRoomStatus,
)


def _with_last_message(queryset):
    """
    Добавляет к queryset chat rooms данные последнего сообщения.

    Используем для компактного отображения room list:
    кто написал последнее сообщение и короткий текст сообщения.
    """
    last_message_qs = ChatMessage.objects.filter(
        room=OuterRef("pk"),
    ).order_by(
        "-created_at",
    )

    return queryset.annotate(
        last_message_text=Subquery(
            last_message_qs.values("text")[:1],
        ),
        last_message_sender_username=Subquery(
            last_message_qs.values("sender__username")[:1],
        ),
    )

def _with_unread_messages_count(queryset, user=None):
    """
    Добавляет к queryset chat rooms количество непрочитанных сообщений.

    Для client/manager считаем только сообщения:
    - которые ещё не прочитаны;
    - которые написал другой пользователь.

    Для admin, когда user=None, считаем все непрочитанные сообщения.
    """
    unread_filter = Q(
        messages__is_read=False,
    )

    if user is not None:
        unread_filter = unread_filter & ~Q(
            messages__sender=user,
        )

    return queryset.annotate(
        unread_messages_count=Count(
            "messages",
            filter=unread_filter,
        )
    )

def get_chat_rooms_for_user(user):
    """
    Возвращает комнаты конкретного клиента.

    Клиент видит только свои chat rooms.
    """
    rooms = ChatRoom.objects.filter(
        user=user,
    ).select_related(
        "user",
        "manager",
        "order",
    ).order_by(
        "-updated_at",
        "-created_at",
    )

    rooms = _with_last_message(rooms)
    rooms = _with_unread_messages_count(
        queryset=rooms,
        user=user,
    )

    return rooms


def get_available_chat_rooms_for_manager():
    """
    Возвращает свободный пул комнат для менеджеров.

    Это OPEN комнаты, которые ещё не взял ни один менеджер.
    """
    rooms = ChatRoom.objects.filter(
        status=ChatRoomStatus.OPEN,
        manager__isnull=True,
    ).select_related(
        "user",
        "manager",
        "order",
    ).order_by(
        "-updated_at",
        "-created_at",
    )

    return _with_last_message(rooms)


def get_active_chat_rooms_for_manager(manager):
    """
    Возвращает активные комнаты конкретного менеджера.

    Это IN_PROGRESS комнаты, которые закреплены за этим менеджером.
    """
    rooms = ChatRoom.objects.filter(
        manager=manager,
        status=ChatRoomStatus.IN_PROGRESS,
    ).select_related(
        "user",
        "manager",
        "order",
    ).order_by(
        "-updated_at",
        "-created_at",
    )

    rooms = _with_last_message(rooms)
    rooms = _with_unread_messages_count(
        queryset=rooms,
        user=manager,
    )

    return rooms


def get_chat_room_messages(room):
    """
    Возвращает сообщения конкретной комнаты.

    Сообщения идут в порядке создания, как обычная история чата.
    """
    return ChatMessage.objects.filter(
        room=room,
    ).select_related(
        "room",
        "sender",
    ).prefetch_related(
        "attachments",
    )


def get_all_chat_rooms_for_admin(user):
    """
    Возвращает все chat rooms для администратора.

    Администратор видит все комнаты независимо от клиента,
    менеджера и статуса.
    """
    rooms = ChatRoom.objects.all().select_related(
        "user",
        "manager",
        "order",
    ).order_by(
        "-updated_at",
        "-created_at",
    )

    rooms = _with_last_message(rooms)
    rooms = _with_unread_messages_count(
        queryset=rooms,
        user=user,
    )

    return rooms

def get_chat_rooms_for_order(order):
    """
    Возвращает chat rooms, связанные с конкретным заказом.

    Используем на странице заказа, чтобы клиент, менеджер
    и администратор видели переписку по этому заказу.
    """
    rooms = ChatRoom.objects.filter(
        order=order,
    ).select_related(
        "user",
        "manager",
        "order",
    ).order_by(
        "-updated_at",
        "-created_at",
    )

    return _with_last_message(rooms)

def get_unread_chat_messages_count_for_user(user):
    """
    Возвращает общее количество непрочитанных chat messages
    для отображения бейджа в navbar.

    Client:
    считает непрочитанные сообщения в своих комнатах,
    кроме собственных сообщений.

    Manager:
    считает непрочитанные сообщения:
    - в OPEN комнатах;
    - в своих IN_PROGRESS комнатах;
    кроме собственных сообщений.

    Admin:
    считает все непрочитанные сообщения,
    кроме собственных сообщений.
    """
    if not user.is_authenticated:
        return 0

    base_queryset = ChatMessage.objects.filter(
        is_read=False,
    ).exclude(
        sender=user,
    )

    if user.role == "client":
        return base_queryset.filter(
            room__user=user,
        ).count()

    if user.role == "manager":
        return base_queryset.filter(
            room__status=ChatRoomStatus.OPEN,
            room__manager__isnull=True,
        ).count() + base_queryset.filter(
            room__status=ChatRoomStatus.IN_PROGRESS,
            room__manager=user,
        ).count()

    if user.role == "admin":
        return base_queryset.count()

    return 0

