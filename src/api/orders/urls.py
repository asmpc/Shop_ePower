from django.urls import path

from api.orders.views import (
    CheckoutAPIView,
    ManagerOrderDetailAPIView,
    ManagerOrderFundAssignmentAPIView,
    ManagerOrderFundAssignmentCancelAPIView,
    ManagerOrderListAPIView,
    ManagerOrderStatusUpdateAPIView,
    OrderCancelAPIView,
    OrderDetailAPIView,
    OrderListAPIView,
)

app_name = "api_orders"


urlpatterns = [
    path("", OrderListAPIView.as_view(), name="list"),
    path("checkout/", CheckoutAPIView.as_view(), name="checkout"),
    path("<int:order_id>/", OrderDetailAPIView.as_view(), name="detail"),
    path("<int:order_id>/cancel/", OrderCancelAPIView.as_view(), name="cancel"),
    path("manage/", ManagerOrderListAPIView.as_view(), name="manage-list"),
    path("manage/<int:order_id>/", ManagerOrderDetailAPIView.as_view(), name="manage-detail"),
    path("manage/<int:order_id>/status/", ManagerOrderStatusUpdateAPIView.as_view(), name="manage-status"),
    path(
        "manage/<int:order_id>/funds/assign/",
        ManagerOrderFundAssignmentAPIView.as_view(),
        name="manage-assign-funds",
    ),
    path(
        "manage/fund-assignments/<int:assignment_id>/cancel/",
        ManagerOrderFundAssignmentCancelAPIView.as_view(),
        name="manage-cancel-fund-assignment",
    ),
]