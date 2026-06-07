from django.db import models


class ChatAttachment(models.Model):
    message = models.ForeignKey(
        "chat.ChatMessage",
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    file = models.FileField(
        upload_to="chat/attachments/",
    )

    original_name = models.CharField(
        max_length=255,
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.original_name