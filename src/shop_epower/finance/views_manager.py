from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.views.generic import DetailView, ListView

from shop_epower.accounts.models import Role
from shop_epower.finance.selectors import (
    get_account_status_history,
    get_account_transactions,
    get_customer_accounts_for_staff,
    get_financial_transactions_for_staff,
)


class ManagerAccountListView(LoginRequiredMixin, ListView):
    template_name = "finance/manage/account_list.html"
    context_object_name = "accounts"
    paginate_by = 20

    def get_queryset(self):
        if self.request.user.role not in (Role.MANAGER, Role.ADMIN):
            raise PermissionDenied

        return get_customer_accounts_for_staff(
            query=self.request.GET.get("q", ""),
            account_id=self.request.GET.get("account_id", ""),
            account_type=self.request.GET.get("account_type", ""),
            status=self.request.GET.get("status", ""),
        )


class ManagerAccountDetailView(LoginRequiredMixin, DetailView):
    template_name = "finance/manage/account_detail.html"
    context_object_name = "account"

    def get_queryset(self):
        if self.request.user.role not in (Role.MANAGER, Role.ADMIN):
            raise PermissionDenied

        return get_customer_accounts_for_staff()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        operations = get_account_transactions(account=self.object)
        paginator = Paginator(operations, 20)
        context["transactions"] = paginator.get_page(
            self.request.GET.get("transactions_page")
        )

        status_changes = get_account_status_history(account=self.object)
        status_paginator = Paginator(status_changes, 20)
        context["status_history"] = status_paginator.get_page(
            self.request.GET.get("status_page")
        )

        return context


class ManagerTransactionListView(LoginRequiredMixin, ListView):
    template_name = "finance/manage/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 20

    def get_queryset(self):
        if self.request.user.role not in (Role.MANAGER, Role.ADMIN):
            raise PermissionDenied

        return get_financial_transactions_for_staff(
            operation_key=self.request.GET.get("operation_key", ""),
        )
