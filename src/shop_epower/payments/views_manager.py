from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView

from shop_epower.orders.models import Order
from shop_epower.orders.navigation import (
    redirect_to_manager_order_detail,
)
from shop_epower.payments.models import (
    Invoice,
    Payment,
)
from shop_epower.payments.navigation import get_safe_manager_payment_list_url
from shop_epower.payments.selectors import (
    get_payments_for_manager,
)
from shop_epower.payments.services import (
    cancel_invoice,
    create_invoice_for_order,
    generate_invoice_pdf,
)


class ManagerPaymentListView(
    LoginRequiredMixin,
    ListView,
):
    model = Payment

    template_name = (
        "payments/manage/payment_list.html"
    )

    context_object_name = "payments"

    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.role not in [
            "manager",
            "admin",
        ]:
            raise PermissionDenied("Manager or admin access required.")

        status = self.request.GET.get("status", "").strip()
        method = self.request.GET.get("method", "").strip()
        provider = self.request.GET.get("provider", "").strip()
        order_id = self.request.GET.get("order_id", "").strip()
        transaction_id = self.request.GET.get("transaction_id", "").strip()
        customer_email = self.request.GET.get("customer_email", "").strip()

        if not (
                status
                or method
                or provider
                or order_id
                or transaction_id
                or customer_email
        ):
            return Payment.objects.none()

        parsed_order_id = None

        if order_id:
            try:
                parsed_order_id = int(order_id)
            except ValueError:
                return Payment.objects.none()

            if not 1 <= parsed_order_id <= 2 ** 63 - 1:
                return Payment.objects.none()

        return get_payments_for_manager(
            status=status,
            method=method,
            provider=provider,
            order_id=parsed_order_id,
            transaction_id=transaction_id or None,
            customer_email=customer_email or None,
        )

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(
            **kwargs,
        )

        context["selected_status"] = (
            self.request.GET.get("status", "").strip()
        )

        context["selected_method"] = (
            self.request.GET.get("method", "").strip()
        )

        context["selected_provider"] = (
            self.request.GET.get("provider", "").strip()
        )

        context["selected_order_id"] = self.request.GET.get(
            "order_id",
            "",
        ).strip()

        context["selected_transaction_id"] = self.request.GET.get(
            "transaction_id",
            "",
        ).strip()

        context["selected_customer_email"] = self.request.GET.get(
            "customer_email",
            "",
        ).strip()

        return context


class ManagerPaymentDetailView(
    LoginRequiredMixin,
    DetailView,
):
    model = Payment

    template_name = (
        "payments/manage/payment_detail.html"
    )

    context_object_name = "payment"

    def get_queryset(self):
        user = self.request.user

        if user.role not in [
            "manager",
            "admin",
        ]:
            raise PermissionDenied("Manager or admin access required.")

        return (
            Payment.objects
            .select_related(
                "order",
                "order__user",
            )
            .prefetch_related(
                "history",
                "history__changed_by",
            )
        )

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(
            **kwargs,
        )

        payment = self.object

        try:
            invoice = payment.invoice
        except Payment.invoice.RelatedObjectDoesNotExist:
            invoice = None

        context["invoice"] = invoice

        context["back_url"] = get_safe_manager_payment_list_url(
            self.request.GET.get("next"),
        )

        return context


class ManagerGenerateInvoiceView(
    LoginRequiredMixin,
    View,
):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in [
            "manager",
            "admin",
        ]:
            return HttpResponseForbidden()

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )

    def post(self, request, *args, **kwargs):
        order = get_object_or_404(
            Order,
            pk=self.kwargs["pk"],
        )

        try:
            create_invoice_for_order(
                order=order,
            )

            messages.success(
                request,
                "Invoice created.",
            )

        except ValidationError as error:
            messages.error(
                request,
                error.message,
            )

        return redirect_to_manager_order_detail(
            request=request,
            order_id=order.pk,
        )


class ManagerCancelInvoiceView(
    LoginRequiredMixin,
    View,
):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ["manager", "admin"]:
            return HttpResponseForbidden()

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )

    def post(self, request, *args, **kwargs):
        invoice = get_object_or_404(
            Invoice,
            pk=self.kwargs["pk"],
        )

        try:
            cancel_invoice(
                invoice=invoice,
                cancelled_by=request.user,
                comment=request.POST.get(
                    "cancel_comment",
                    "",
                ),
            )

            messages.success(
                request,
                "Invoice cancelled.",
            )

        except ValidationError as error:
            messages.error(
                request,
                error.message,
            )

        return redirect_to_manager_order_detail(
            request=request,
            order_id=invoice.order_id,
        )


class ManagerInvoicePdfView(
    LoginRequiredMixin,
    View,
):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in [
            "manager",
            "admin",
        ]:
            return HttpResponseForbidden()

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )

    def get(self, request, *args, **kwargs):
        invoice = get_object_or_404(
            Invoice.objects
            .select_related(
                "order",
                "payment",
            )
            .prefetch_related(
                "order__items",
            ),
            pk=self.kwargs["pk"],
        )

        pdf = generate_invoice_pdf(
            invoice=invoice,
        )

        response = HttpResponse(
            pdf,
            content_type="application/pdf",
        )

        response["Content-Disposition"] = (
            f'attachment; filename="{invoice.invoice_number}.pdf"'
        )

        return response