from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
)
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.views import View

from urllib.parse import urlencode

from shop_epower.payments.models import (
    Invoice,
    Payment,
)

from shop_epower.payments.selectors import (
    get_payments_for_manager,
)
from shop_epower.payments.validators import (
    validate_manager_can_create_invoice,
)

from shop_epower.payments.services import (
    create_invoice_for_payment,
    cancel_invoice,
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

    def get_queryset(self):
        user = self.request.user

        if user.role not in [
            "manager",
            "admin",
        ]:
            return Payment.objects.none()

        return get_payments_for_manager(
            status=self.request.GET.get("status"),
            method=self.request.GET.get("method"),
            provider=self.request.GET.get("provider"),
        )

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(
            **kwargs,
        )

        context["selected_status"] = (
            self.request.GET.get("status", "")
        )

        context["selected_method"] = (
            self.request.GET.get("method", "")
        )

        context["selected_provider"] = (
            self.request.GET.get("provider", "")
        )

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
            return Payment.objects.none()

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

        context["back_url"] = self.request.GET.get(
            "next",
            reverse("payments:manager_payment_list"),
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
        payment = get_object_or_404(
            Payment.objects.select_related(
                "order",
            ),
            pk=self.kwargs["pk"],
        )

        try:
            validate_manager_can_create_invoice(
                payment=payment,
            )

            create_invoice_for_payment(
                payment=payment,
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

        return redirect(
            "orders:manager_order_detail",
            pk=payment.order.pk,
        )


class AdminCancelInvoiceView(
    LoginRequiredMixin,
    View,
):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "admin":
            return HttpResponseForbidden()

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )

    def post(self, request, *args, **kwargs):
        invoice = get_object_or_404(
            Invoice.objects.select_related(
                "payment",
                "order",
            ),
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

        payment_detail_url = reverse(
            "payments:manager_payment_detail",
            args=[invoice.payment_id],
        )

        next_url = request.POST.get(
            "next",
            reverse(
                "orders:manager_order_detail",
                args=[invoice.order_id],
            ),
        )

        query_string = urlencode(
            {
                "next": next_url,
            }
        )

        return redirect(
            f"{payment_detail_url}?{query_string}",
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