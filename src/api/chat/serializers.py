from rest_framework import serializers

from shop_epower.chat.models import (
    ChatMessage,
    ChatRoom,
)


class ChatRoomSerializer(serializers.ModelSerializer):
    last_message_text = serializers.CharField(
        read_only=True,
    )
    last_message_sender_username = serializers.CharField(
        read_only=True,
    )
    unread_messages_count = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = ChatRoom
        fields = (
            "id",
            "user",
            "manager",
            "order",
            "status",
            "created_at",
            "updated_at",
            "closed_at",
            "last_message_text",
            "last_message_sender_username",
            "unread_messages_count",
        )


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(
        source="sender.username",
        read_only=True,
    )

    class Meta:
        model = ChatMessage
        fields = (
            "id",
            "room",
            "sender",
            "sender_username",
            "text",
            "is_read",
            "created_at",
        )