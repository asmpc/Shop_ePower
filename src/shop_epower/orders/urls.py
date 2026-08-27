from django.urls import path

from shop_epower.orders.views_manager import (
    AdminResetPaymentToPendingView,
    ManagerMarkPaymentCancelledView,
    ManagerMarkPaymentFailedView,
    ManagerMarkPaymentPaidView,
    ManagerOrderDeliveryUpdateView,
    ManagerOrderDetailView,
    ManagerOrderListView,
    ManagerOrderStatusUpdateView,
)

from .views import (
    checkout_view,
    order_cancel_view,
    order_detail_view,
    order_list_view,
    order_success_view,
)

app_name = "orders"

urlpatterns = [
    path("checkout/", checkout_view, name="checkout"),
    path("success/<int:order_id>/", order_success_view, name="success"),
    path("", order_list_view, name="list"),
    path("<int:order_id>/", order_detail_view, name="detail"),
    path("<int:order_id>/cancel/", order_cancel_view, name="cancel"),
    path(
        "manage/",
        ManagerOrderListView.as_view(),
        name="manager_order_list",
    ),

    path(
        "manage/<int:pk>/",
        ManagerOrderDetailView.as_view(),
        name="manager_order_detail",
    ),
    path(
        "manage/<int:pk>/status/",
        ManagerOrderStatusUpdateView.as_view(),
        name="manager_order_status_update",
    ),
    path(
        "manage/<int:pk>/delivery/",
        ManagerOrderDeliveryUpdateView.as_view(),
        name="manager_order_delivery_update",
    ),

    path(
        "manage/orders/<int:pk>/payment/mark-paid/",
        ManagerMarkPaymentPaidView.as_view(),
        name="manager_mark_payment_paid",
    ),

    path(
        "manage/orders/<int:pk>/payment/mark-failed/",
        ManagerMarkPaymentFailedView.as_view(),
        name="manager_mark_payment_failed",
    ),

    path(
        "manage/orders/<int:pk>/payment/mark-cancelled/",
        ManagerMarkPaymentCancelledView.as_view(),
        name="manager_mark_payment_cancelled",
    ),
    path(
        "manage/orders/<int:pk>/payment/reset-to-pending/",
        AdminResetPaymentToPendingView.as_view(),
        name="admin_reset_payment_to_pending",
    ),

]