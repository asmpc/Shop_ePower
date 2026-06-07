from django.conf import settings
from django.db import models


class ChatMessage(models.Model):
    room = models.ForeignKey(
        "chat.ChatRoom",
        on_delete=models.CASCADE,
        related_name="messages",
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )

    text = models.TextField()

    is_read = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message #{self.pk} in room #{self.room_id}"