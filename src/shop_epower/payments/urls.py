from django.urls import path

from shop_epower.payments.views import (
    client_invoice_pdf_view,
    mock_checkout_view,
    mock_payment_success_view,
)
from shop_epower.payments.views_manager import (
    ManagerCancelInvoiceView,
    ManagerGenerateInvoiceView,
    ManagerInvoicePdfView,
    ManagerPaymentDetailView,
    ManagerPaymentListView,
    ManagerRecordReceiptView,
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
        "manage/orders/<int:pk>/receipts/new/",
        ManagerRecordReceiptView.as_view(),
        name="manager_record_receipt",
    ),

    path(
        "manage/orders/<int:pk>/generate-invoice/",
        ManagerGenerateInvoiceView.as_view(),
        name="manager_generate_invoice",
    ),

    path(
        "manage/invoices/<int:pk>/cancel/",
        ManagerCancelInvoiceView.as_view(),
        name="manager_cancel_invoice",
    ),

    path(
        "manage/invoices/<int:pk>/pdf/",
        ManagerInvoicePdfView.as_view(),
        name="manager_invoice_pdf",
    ),


]