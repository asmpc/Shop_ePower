from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from shop_epower.chat.models import ChatRoom, ChatMessage
from .serializers import ChatRoomSerializer, ChatMessageSerializer
from shop_epower.chat.selectors import get_chat_room_messages
from shop_epower.chat.services import take_chat_room, close_chat_room, send_chat_message


class ChatRoomViewSet(viewsets.ModelViewSet):
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role in ["manager", "admin"]:
            from shop_epower.chat.selectors import get_all_chat_rooms_for_admin
            return get_all_chat_rooms_for_admin(user=user)
        else:
            from shop_epower.chat.selectors import get_chat_rooms_for_user
            return get_chat_rooms_for_user(user)

    # take action
    @action(detail=True, methods=["post"])
    def take(self, request, pk=None):
        room = self.get_object()
        try:
            take_chat_room(room=room, manager=request.user)  # здесь manager, а не user
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(room)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """
        Закрывает чат-комнату.
        Клиент может закрывать свои комнаты.
        Менеджер — только комнаты, которые он взял.
        """
        room = self.get_object()

        # Определяем кто закрывает: клиент или менеджер
        if request.user.role in ["manager", "admin"]:
            manager = request.user
        else:
            manager = None

        try:
            close_chat_room(room=room, manager=manager)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(room)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        room = self.get_object()
        text = request.data.get("text", "")
        try:
            send_chat_message(room=room, sender=request.user, text=text)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        messages_qs = get_chat_room_messages(room)
        serializer = ChatMessageSerializer(messages_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        room = self.get_object()
        messages_qs = get_chat_room_messages(room)
        serializer = ChatMessageSerializer(messages_qs, many=True)
        return Response(serializer.data)