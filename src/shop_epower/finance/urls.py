from django.urls import path

from shop_epower.finance.views_manager import (
    ManagerAccountDetailView,
    ManagerAccountListView,
    ManagerTransactionListView,
)

app_name = "finance"

urlpatterns = [
    path(
        "manage/accounts/",
        ManagerAccountListView.as_view(),
        name="manager_account_list",
    ),
    path(
        "manage/accounts/<int:pk>/",
        ManagerAccountDetailView.as_view(),
        name="manager_account_detail",
    ),
    path(
        "manage/transactions/",
        ManagerTransactionListView.as_view(),
        name="manager_transaction_list",
    ),
]
