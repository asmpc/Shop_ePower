from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.urls import reverse

from shop_epower.payments.models import Payment
from shop_epower.payments.selectors import (
    get_payments_for_manager,
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

        context["back_url"] = self.request.GET.get(
            "next",
            reverse("payments:manager_payment_list"),
        )

        return context