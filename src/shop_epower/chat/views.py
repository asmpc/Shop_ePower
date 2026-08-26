from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from shop_epower.chat.forms import (
    ChatMessageForm,
    ChatRoomCreateForm,
)
from shop_epower.chat.models import ChatRoom, ChatRoomStatus
from shop_epower.chat.selectors import (
    get_active_chat_rooms_for_manager,
    get_all_chat_rooms_for_admin,
    get_available_chat_rooms_for_manager,
    get_chat_room_messages,
    get_chat_rooms_for_user,
)
from shop_epower.chat.services import (
    close_chat_room,
    close_chat_room_by_client,
    create_chat_room,
    mark_messages_as_read,
    send_chat_message,
    take_chat_room,
)


def _check_room_access(user, room):
    if user.role == "admin":
        return

    if user.role == "manager":
        if room.status == ChatRoomStatus.OPEN:
            return

        if room.manager == user:
            return

        raise PermissionDenied

    if user.role == "client":
        if room.user == user:
            return

        raise PermissionDenied

    raise PermissionDenied


@login_required
def room_list(request):
    user = request.user
    status_filter = request.GET.get("status")

    if user.role == "admin":
        rooms = get_all_chat_rooms_for_admin(user=user)
        if status_filter and status_filter != "all":
            rooms = rooms.filter(status=status_filter)
        return render(request, "chat/room_list.html", {"rooms": rooms})

    if user.role == "manager":
        available_rooms = get_available_chat_rooms_for_manager()
        active_rooms = get_active_chat_rooms_for_manager(user)

        if status_filter and status_filter != "all":
            if status_filter == "open":
                available_rooms = available_rooms.filter(status="open")
            elif status_filter == "in_progress":
                active_rooms = active_rooms.filter(status="in_progress")
            elif status_filter == "closed":
                available_rooms = available_rooms.filter(status="closed")
                active_rooms = active_rooms.filter(status="closed")

        return render(
            request,
            "chat/room_list.html",
            {
                "available_rooms": available_rooms,
                "active_rooms": active_rooms,
            },
        )

    rooms = get_chat_rooms_for_user(user)
    if status_filter and status_filter != "all":
        rooms = rooms.filter(status=status_filter)
    return render(request, "chat/room_list.html", {"rooms": rooms})


@login_required
def room_create(request):
    if request.user.role == "manager":
        raise PermissionDenied

    initial_order_id = request.GET.get("order")

    if request.method == "POST":
        form = ChatRoomCreateForm(
            data=request.POST,
            user=request.user,
        )

        if form.is_valid():
            room = create_chat_room(
                user=request.user,
                order=form.cleaned_data["order"],
            )

            return redirect(
                "chat:room_detail",
                pk=room.pk,
            )

    else:
        form = ChatRoomCreateForm(
            user=request.user,
            initial={
                "order": initial_order_id,
            },
        )

    return render(
        request,
        "chat/room_create.html",
        {
            "form": form,
        },
    )


@login_required
def room_detail(request, pk):
    room = get_object_or_404(
        ChatRoom.objects.select_related(
            "user",
            "manager",
            "order",
        ),
        pk=pk,
    )

    _check_room_access(
        request.user,
        room,
    )

    if room.status != ChatRoomStatus.OPEN:
        if request.user == room.user or request.user == room.manager:
            mark_messages_as_read(
                room=room,
                user=request.user,
            )

    chat_messages = get_chat_room_messages(room)
    form = ChatMessageForm()

    return render(
        request,
        "chat/room_detail.html",
        {
            "room": room,
            "chat_messages": chat_messages,
            "form": form,
        },
    )

@login_required
def room_take(request, pk):
    if request.user.role not in ("manager", "admin"):
        raise PermissionDenied

    room = get_object_or_404(
        ChatRoom,
        pk=pk,
    )

    if request.method != "POST":
        raise PermissionDenied

    try:
        take_chat_room(
            room=room,
            manager=request.user,
        )
    except ValueError as error:
        raise PermissionDenied from error

    return redirect(
        "chat:room_detail",
        pk=room.pk,
    )


@login_required
def room_close(request, pk):
    room = get_object_or_404(
        ChatRoom,
        pk=pk,
    )

    if request.method != "POST":
        raise PermissionDenied

    if room.status == ChatRoomStatus.CLOSED:
        raise PermissionDenied

    try:
        if request.user.role == "client":
            close_chat_room_by_client(
                room=room,
                user=request.user,
            )

        elif request.user.role in ("manager", "admin"):
            close_chat_room(
                room=room,
                manager=request.user,
            )

        else:
            raise PermissionDenied

    except (PermissionError, ValueError) as error:
        raise PermissionDenied from error

    return redirect(
        "chat:room_detail",
        pk=room.pk,
    )

@login_required
def room_send(request, pk):
    room = get_object_or_404(
        ChatRoom,
        pk=pk,
    )

    if request.method != "POST":
        raise PermissionDenied

    _check_room_access(request.user, room)

    form = ChatMessageForm(
        data=request.POST,
        files=request.FILES,
    )

    if not form.is_valid():
        return redirect(
            "chat:room_detail",
            pk=room.pk,
        )

    try:
        send_chat_message(
            room=room,
            sender=request.user,
            text=form.cleaned_data["text"],
            files=request.FILES.getlist("files"),
        )
    except PermissionDenied:
        raise

    return redirect(
        "chat:room_detail",
        pk=room.pk,
    )