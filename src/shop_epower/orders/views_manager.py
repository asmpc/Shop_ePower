from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from shop_epower.chat.selectors import get_chat_rooms_for_order
from shop_epower.orders.models import (
    Order,
    OrderStatus,
)
from shop_epower.orders.navigation import (
    redirect_to_manager_order_detail,
)
from shop_epower.orders.services import (
    update_order_delivery_by_manager,
    update_order_status_by_manager,
)
from shop_epower.payments.models import (
    PaymentMethod,
)
from shop_epower.payments.selectors import (
    get_invoice_workflow_state,
)
from shop_epower.payments.services import (
    mark_payment_cancelled,
    mark_payment_failed,
    mark_payment_paid,
    reset_payment_to_pending,
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

        if user.role not in [
            "manager",
            "admin",
        ]:
            return Order.objects.none()

        qs = (
            Order.objects
            .select_related(
                "user",
                "payment",
                "payment__invoice",
            )
            .prefetch_related(
                "items",
            )
        )

        status = self.request.GET.get(
            "status",
            "all",
        )

        if status != "all":
            qs = qs.filter(
                status=status,
            )

        return qs

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(
            **kwargs,
        )

        context["waiting_invoices_count"] = (
            Order.objects
            .filter(
                payment__method=PaymentMethod.INVOICE,
                payment__invoice__isnull=True,
            )
            .exclude(
                status__in=[
                    OrderStatus.COMPLETED,
                    OrderStatus.CANCELLED,
                ],
            )
            .count()
        )

        return context


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
            .select_related(
                "user",
                "payment",
                "payment__invoice",
            )
            .prefetch_related("items")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["chat_rooms"] = get_chat_rooms_for_order(
            self.object,
        )

        context["back_url"] = self.request.GET.get(
            "next",
            reverse("orders:manager_order_list"),
        )

        try:
            context["payment"] = self.object.payment
        except Order.payment.RelatedObjectDoesNotExist:
            context["payment"] = None

        context["invoice_workflow_state"] = None

        if (
                context["payment"]
                and context["payment"].method == PaymentMethod.INVOICE
                and not hasattr(
            context["payment"],
            "invoice",
        )
        ):
            context["invoice_workflow_state"] = (
                get_invoice_workflow_state(
                    order=self.object,
                )
            )

        return context


class ManagerPaymentActionMixin(
    LoginRequiredMixin,
):
    def dispatch(self, request, *args, **kwargs):

        if request.user.role not in ["manager", "admin"]:
            return HttpResponseForbidden()

        return super().dispatch(request, *args, **kwargs)

    def get_order(self):
        return get_object_or_404(
            Order.objects.select_related("payment"),
            pk=self.kwargs["pk"],
        )

    def get_success_response(
            self,
            request,
    ):
        return redirect_to_manager_order_detail(
            request=request,
            order_id=self.kwargs["pk"],
        )


class AdminPaymentActionMixin(
    LoginRequiredMixin,
):
    def dispatch(self, request, *args, **kwargs):

        if request.user.role != "admin":
            return HttpResponseForbidden()

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )

    def get_order(self):
        return get_object_or_404(
            Order.objects.select_related("payment"),
            pk=self.kwargs["pk"],
        )

    def get_success_response(
            self,
            request,
    ):
        return redirect_to_manager_order_detail(
            request=request,
            order_id=self.kwargs["pk"],
        )


class AdminResetPaymentToPendingView(
    AdminPaymentActionMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        order = self.get_order()

        try:
            reset_payment_to_pending(
                payment=order.payment,
                comment=request.POST.get(
                    "manager_comment",
                    "",
                ),
                changed_by=request.user,
            )

            messages.success(
                request,
                "Payment reset to pending.",
            )

        except ValidationError as error:
            messages.error(
                request,
                error.message,
            )

        return self.get_success_response(
            request,
        )


class ManagerMarkPaymentPaidView(
    ManagerPaymentActionMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        order = self.get_order()

        mark_payment_paid(
            payment=order.payment,
            manager_comment=request.POST.get("manager_comment", ""),
            changed_by=request.user,
        )

        return self.get_success_response(
            request,
        )


class ManagerMarkPaymentFailedView(
    ManagerPaymentActionMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        order = self.get_order()

        mark_payment_failed(
            payment=order.payment,
            manager_comment=request.POST.get("manager_comment", ""),
            changed_by=request.user,
        )

        return self.get_success_response(
            request,
        )


class ManagerMarkPaymentCancelledView(
    ManagerPaymentActionMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        order = self.get_order()

        mark_payment_cancelled(
            payment=order.payment,
            manager_comment=request.POST.get("manager_comment", ""),
            changed_by=request.user,
        )

        return self.get_success_response(
            request,
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

        return redirect_to_manager_order_detail(
            request=request,
            order_id=order.id,
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

        delivery_method = request.POST.get(
            "delivery_method",
            "pickup",
        )

        delivery_provider = request.POST.get(
            "delivery_provider",
            "",
        )

        delivery_address = request.POST.get(
            "delivery_address",
            "",
        )

        delivery_comment = request.POST.get(
            "delivery_comment",
            "",
        )

        manager_delivery_comment = request.POST.get(
            "manager_delivery_comment",
            "",
        )

        try:
            update_order_delivery_by_manager(
                order=order,
                user=request.user,
                delivery_method=delivery_method,
                delivery_provider=delivery_provider,
                delivery_address=delivery_address,
                delivery_comment=delivery_comment,
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

        return redirect_to_manager_order_detail(
            request=request,
            order_id=order.id,
        )