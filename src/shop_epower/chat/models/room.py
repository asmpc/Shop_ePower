from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatRoomStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In progress"
    CLOSED = "closed", "Closed"


class ChatRoom(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_rooms",
    )

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="managed_chat_rooms",
        null=True,
        blank=True,
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        related_name="chat_rooms",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=ChatRoomStatus.choices,
        default=ChatRoomStatus.OPEN,
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return f"Chat room #{self.pk} — {self.status}"

    def close(self):
        self.status = ChatRoomStatus.CLOSED
        self.closed_at = timezone.now()