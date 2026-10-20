from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView

from shop_epower.chat.selectors import get_chat_rooms_for_order
from shop_epower.orders.models import (
    Order,
    OrderStatus,
)
from shop_epower.orders.navigation import (
    get_safe_manager_order_return_url,
    redirect_to_manager_order_detail,
)
from shop_epower.orders.services import (
    update_order_delivery_by_manager,
    update_order_status_by_manager,
)
from shop_epower.payments.models import (
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)
from shop_epower.payments.selectors import (
    get_active_invoice_for_order,
    get_invoice_workflow_state,
    get_invoices_for_order,
)
from shop_epower.payments.services import (
    mark_payment_cancelled,
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

    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.role not in ["manager", "admin"]:
            raise PermissionDenied("Manager or admin access required.")


        issued_invoices = Invoice.objects.filter(
            order_id=OuterRef("pk"),
            status=InvoiceStatus.ISSUED,
        )

        qs = (
            Order.objects
            .select_related(
                "user",
            )
            .annotate(
                has_active_invoice=Exists(issued_invoices),
            )
        )

        status = self.request.GET.get("status", "active")

        if status == "active":
            qs = qs.filter(
                status__in=[
                    OrderStatus.NEW,
                    OrderStatus.PROCESSING,
                ],
            )
        else:
            qs = qs.filter(status=status)

        return qs.order_by("-created_at", "-pk")

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(
            **kwargs,
        )

        context["waiting_invoices_count"] = (
            Order.objects
            .annotate(
                has_active_invoice=Exists(
                    Invoice.objects.filter(
                        order_id=OuterRef("pk"),
                        status=InvoiceStatus.ISSUED,
                    ),
                ),
            )
            .filter(
                payment_method=PaymentMethod.INVOICE,
                status__in=[
                    OrderStatus.NEW,
                    OrderStatus.PROCESSING,
                ],
                has_active_invoice=False,
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
            raise PermissionDenied("Manager or admin access required.")

        return (
            Order.objects
            .select_related(
                "user",
            )
            .prefetch_related(
                "items",
                "payments",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        payments = self.object.payments.all()
        invoice = get_active_invoice_for_order(
            order=self.object,
        )
        invoice_required = (
                self.object.payment_method == PaymentMethod.INVOICE
        )

        context["payments"] = payments
        context["invoice"] = invoice
        context["invoice_required"] = invoice_required

        context["chat_rooms"] = get_chat_rooms_for_order(
            self.object,
        )

        context["back_url"] = get_safe_manager_order_return_url(
            self.request.GET.get("next"),
            payment_ids=[payment.pk for payment in payments],
        )

        context["invoice_workflow_state"] = None

        if invoice_required and invoice is None:
            context["invoice_workflow_state"] = get_invoice_workflow_state(
                order=self.object,
            )

        invoice_history = get_invoices_for_order(
            order=self.object,
        )
        invoice_paginator = Paginator(
            invoice_history,
            20,
        )

        context["invoice_history"] = invoice_paginator.get_page(
            self.request.GET.get("invoices_page"),
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
            Order,
            pk=self.kwargs["pk"],
        )

    def get_payment(self):
        order = self.get_order()

        try:
            payment_id = int(
                self.request.POST.get("payment_id"),
            )
        except (TypeError, ValueError) as error:
            raise Http404("Invalid payment ID.") from error

        return get_object_or_404(
            Payment,
            pk=payment_id,
            order=order,
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
    ManagerPaymentActionMixin,
):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "admin":
            return HttpResponseForbidden()

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )


class AdminResetPaymentToPendingView(
    AdminPaymentActionMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        payment = self.get_payment()

        try:
            reset_payment_to_pending(
                payment=payment,
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
        payment = self.get_payment()

        mark_payment_paid(
            payment=payment,
            manager_comment=request.POST.get(
                "manager_comment",
                "",
            ),
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
        payment = self.get_payment()

        mark_payment_cancelled(
            payment=payment,
            manager_comment=request.POST.get(
                "manager_comment",
                "",
            ),
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

        if request.user.role not in ["manager", "admin"]:
            raise PermissionDenied(
                "Manager or admin access required."
            )

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