from urllib.parse import urlsplit
from uuid import uuid4

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import QueryDict
from django.views.generic import DetailView, ListView

from shop_epower.accounts.models import Role
from shop_epower.finance.navigation import (
    get_safe_manager_account_detail_url,
    get_safe_manager_account_list_url,
)
from shop_epower.finance.selectors import (
    get_account_status_history,
    get_account_transactions,
    get_customer_account_balances,
    get_customer_accounts_for_staff,
    get_financial_transactions_for_staff,
)
from shop_epower.payments.forms import (
    ManualAccountPayoutForm,
    ManualPaymentReceiptForm,
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

def get_manager_account_detail_context(
    *,
    request,
    account,
    form=None,
    active_action=None,
    return_url=None,
):
    """Готовит страницу счёта для открытия и повторного показа с ошибками."""
    if return_url is None:
        return_url = request.get_full_path()

    return_url = get_safe_manager_account_detail_url(
        return_url,
        account=account,
    )
    parsed_return_url = urlsplit(return_url)
    query_params = QueryDict(parsed_return_url.query)

    context = {
        "account": (
            get_customer_account_balances(
                user=account.user,
            )
            .select_related("user")
            .get(pk=account.pk)
        ),
        "back_url": get_safe_manager_account_list_url(
            query_params.get("next"),
        ),
        "return_url": return_url,
        "account_detail_url": parsed_return_url.path,
        "account_query": query_params,
    }

    operations = get_account_transactions(account=account)
    paginator = Paginator(operations, 20)
    context["transactions"] = paginator.get_page(
        query_params.get("transactions_page"),
    )

    status_changes = get_account_status_history(account=account)
    status_paginator = Paginator(status_changes, 20)
    context["status_history"] = status_paginator.get_page(
        query_params.get("status_page"),
    )

    receipt_form_open = (
        form is not None
        and active_action == "receipt"
    )

    if receipt_form_open:
        receipt_form = form
    else:
        receipt_form = ManualPaymentReceiptForm(
            initial={
                "operation_key": f"manual-account-receipt:{uuid4()}",
            },
            auto_id=f"id_account_{account.pk}_receipt_%s",
        )

    context["receipt_form"] = receipt_form
    context["receipt_form_open"] = receipt_form_open

    payout_form_open = (
        form is not None
        and active_action == "payout"
    )

    if payout_form_open:
        payout_form = form
    else:
        payout_form = ManualAccountPayoutForm(
            initial={
                "operation_key": f"manual-account-payout:{uuid4()}",
            },
            auto_id=f"id_account_{account.pk}_payout_%s",
        )

    context["payout_form"] = payout_form
    context["payout_form_open"] = payout_form_open

    if form is not None:
        context["form"] = form

    return context


class ManagerAccountDetailView(LoginRequiredMixin, DetailView):
    template_name = "finance/manage/account_detail.html"
    context_object_name = "account"

    def get_queryset(self):
        if self.request.user.role not in (Role.MANAGER, Role.ADMIN):
            raise PermissionDenied

        return get_customer_accounts_for_staff()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            get_manager_account_detail_context(
                request=self.request,
                account=self.object,
            ),
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
