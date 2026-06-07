from django.contrib import admin

from shop_epower.chat.models import (
    ChatAttachment,
    ChatMessage,
    ChatRoom,
)


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = (
        "sender",
        "text",
        "is_read",
        "created_at",
    )

    can_delete = False


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "manager",
        "order",
        "status",
        "created_at",
        "updated_at",
        "closed_at",
    )

    list_filter = (
        "status",
        "created_at",
        "updated_at",
        "closed_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "manager__email",
        "manager__username",
        "order__id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "closed_at",
    )

    inlines = [
        ChatMessageInline,
    ]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "sender",
        "is_read",
        "created_at",
    )

    list_filter = (
        "is_read",
        "created_at",
    )

    search_fields = (
        "sender__email",
        "sender__username",
        "text",
        "room__id",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(ChatAttachment)
class ChatAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "original_name",
        "uploaded_at",
    )

    search_fields = (
        "original_name",
        "message__id",
    )

    readonly_fields = (
        "uploaded_at",
    )