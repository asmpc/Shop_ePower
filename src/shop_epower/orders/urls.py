from django.urls import path
from .views import (
    checkout_view,
    order_success_view,
    order_list_view,
    order_detail_view,
    order_cancel_view,
)

from shop_epower.orders.views_manager import (
    ManagerOrderListView,
    ManagerOrderDetailView,
    ManagerOrderStatusUpdateView,
    ManagerOrderDeliveryUpdateView,
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
]