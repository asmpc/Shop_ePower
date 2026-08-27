from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.chat.views import ChatRoomViewSet

app_name = "chat_api"

router = DefaultRouter()
router.register(
    "rooms",
    ChatRoomViewSet,
    basename="chat-room",
)

urlpatterns = [
    path("", include(router.urls)),
]