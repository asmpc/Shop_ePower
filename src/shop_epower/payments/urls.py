from django.urls import path

from shop_epower.payments.views import (
    client_invoice_pdf_view,
    mock_checkout_view,
    mock_payment_fail_view,
    mock_payment_success_view,
)
from shop_epower.payments.views_manager import (
    AdminCancelInvoiceView,
    ManagerGenerateInvoiceView,
    ManagerInvoicePdfView,
    ManagerPaymentDetailView,
    ManagerPaymentListView,
)

app_name = "payments"


urlpatterns = [
    path(
        "mock/<str:transaction_id>/",
        mock_checkout_view,
        name="mock_checkout",
    ),

    path(
        "mock/<str:transaction_id>/success/",
        mock_payment_success_view,
        name="mock_payment_success",
    ),

    path(
        "mock/<str:transaction_id>/fail/",
        mock_payment_fail_view,
        name="mock_payment_fail",
    ),

    path(
        "invoices/<int:pk>/pdf/",
        client_invoice_pdf_view,
        name="client_invoice_pdf",
    ),

    path(
        "manage/",
        ManagerPaymentListView.as_view(),
        name="manager_payment_list",
    ),

    path(
        "manage/<int:pk>/",
        ManagerPaymentDetailView.as_view(),
        name="manager_payment_detail",
    ),

    path(
        "manage/<int:pk>/generate-invoice/",
        ManagerGenerateInvoiceView.as_view(),
        name="manager_generate_invoice",
    ),

    path(
        "manage/invoices/<int:pk>/cancel/",
        AdminCancelInvoiceView.as_view(),
        name="admin_cancel_invoice",
    ),

    path(
        "manage/invoices/<int:pk>/pdf/",
        ManagerInvoicePdfView.as_view(),
        name="manager_invoice_pdf",
    ),


]