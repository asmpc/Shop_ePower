from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView

from shop_epower.orders.models import Order
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.core.exceptions import ValidationError

from shop_epower.orders.services import (
    update_order_status_by_manager,
    update_order_delivery_by_manager,
)



class ManagerOrderListView(
    LoginRequiredMixin,
    ListView,
):
    model = Order

    template_name = "orders/manage/order_list.html"

    context_object_name = "orders"

    ordering = ["-created_at"]

    def get_queryset(self):

        user = self.request.user

        if user.role not in ["manager", "admin"]:
            return Order.objects.none()

        return (
            Order.objects
            .select_related("user")
            .prefetch_related("items")
        )


class ManagerOrderDetailView(
    LoginRequiredMixin,
    DetailView,
):
    model = Order

    template_name = "orders/manage/order_detail.html"

    context_object_name = "order"

    def get_queryset(self):

        user = self.request.user

        if user.role not in ["manager", "admin"]:
            return Order.objects.none()

        return (
            Order.objects
            .select_related("user")
            .prefetch_related("items")
        )

class ManagerOrderStatusUpdateView(
    LoginRequiredMixin,
    View,
):

    def post(self, request, pk):

        order = get_object_or_404(
            Order,
            pk=pk,
        )

        new_status = request.POST.get("status")

        cancellation_reason = request.POST.get(
            "cancellation_reason",
            "",
        )

        cancellation_comment = request.POST.get(
            "cancellation_comment",
            "",
        )

        try:
            update_order_status_by_manager(
                order=order,
                user=request.user,
                new_status=new_status,
                cancellation_reason=cancellation_reason,
                cancellation_comment=cancellation_comment,
            )

            messages.success(
                request,
                "Order status updated successfully.",
            )

        except ValidationError as error:
            messages.error(
                request,
                error.message,
            )

        return redirect(
            "orders:manager_order_detail",
            pk=order.pk,
        )

class ManagerOrderDeliveryUpdateView(
    LoginRequiredMixin,
    View,
):

    def post(self, request, pk):

        order = get_object_or_404(
            Order,
            pk=pk,
        )

        delivery_cost = request.POST.get(
            "delivery_cost",
            "0",
        )

        delivery_paid_by_customer_on_receipt = (
            request.POST.get(
                "delivery_paid_by_customer_on_receipt",
            ) == "on"
        )

        manager_delivery_comment = request.POST.get(
            "manager_delivery_comment",
            "",
        )

        try:
            update_order_delivery_by_manager(
                order=order,
                user=request.user,
                delivery_cost=delivery_cost,
                delivery_paid_by_customer_on_receipt=delivery_paid_by_customer_on_receipt,
                manager_delivery_comment=manager_delivery_comment,
            )

            messages.success(
                request,
                "Delivery information updated successfully.",
            )

        except ValidationError as error:
            messages.error(
                request,
                error.message,
            )

        return redirect(
            "orders:manager_order_detail",
            pk=order.pk,
        )