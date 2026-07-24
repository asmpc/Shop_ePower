from django.urls import path

from api.payments.views import (
    ClientPaymentDetailAPIView,
    ClientPaymentHistoryAPIView,
    ClientPaymentInvoiceAPIView,
    ClientPaymentInvoicePDFAPIView,
    ClientPaymentListAPIView,
    ManagerPaymentListAPIView,
    ManagerPaymentDetailAPIView,
    ManagerPaymentMarkPaidAPIView,
    ManagerPaymentMarkFailedAPIView,
    ManagerPaymentMarkCancelledAPIView,
    ManagerPaymentResetToPendingAPIView,
    ManagerPaymentHistoryAPIView,
    ManagerInvoiceCreateAPIView,
    ManagerInvoiceDetailAPIView,
    ManagerInvoicePdfAPIView,
    ManagerInvoiceCancelAPIView,

)


app_name = 'api-payments'


urlpatterns = [
    path(
        'my/',
        ClientPaymentListAPIView.as_view(),
        name='client-payment-list',
    ),

    path(
        'my/<int:payment_id>/',
        ClientPaymentDetailAPIView.as_view(),
        name='client-payment-detail',
    ),

    path(
        'my/<int:payment_id>/history/',
        ClientPaymentHistoryAPIView.as_view(),
        name='client-payment-history',
    ),

    path(
        "my/<int:payment_id>/invoice/",
        ClientPaymentInvoiceAPIView.as_view(),
        name="client-payment-invoice",
    ),

    path(
        "my/<int:payment_id>/invoice/pdf/",
        ClientPaymentInvoicePDFAPIView.as_view(),
        name="client-payment-invoice-pdf",
    ),

    path(
        "manage/",
        ManagerPaymentListAPIView.as_view(),
        name="manager-payment-list",
    ),

    path(
        "manage/<int:pk>/",
        ManagerPaymentDetailAPIView.as_view(),
        name="manager-payment-detail",
    ),

    path(
        "manage/<int:pk>/mark-paid/",
        ManagerPaymentMarkPaidAPIView.as_view(),
        name="manager-payment-mark-paid",
    ),

    path(
        "manage/<int:pk>/mark-failed/",
        ManagerPaymentMarkFailedAPIView.as_view(),
        name="manager-payment-mark-failed",
    ),

    path(
        "manage/<int:pk>/mark-cancelled/",
        ManagerPaymentMarkCancelledAPIView.as_view(),
        name="manager-payment-mark-cancelled",
    ),

    path(
        "manage/<int:pk>/reset-to-pending/",
        ManagerPaymentResetToPendingAPIView.as_view(),
        name="manager-payment-reset-to-pending",
    ),

    path(
        "manage/<int:pk>/history/",
        ManagerPaymentHistoryAPIView.as_view(),
        name="manager-payment-history",
    ),

    path(
        "manage/<int:payment_id>/invoice/",
        ManagerInvoiceCreateAPIView.as_view(),
        name="manager-invoice-create",
    ),

    path(
        "manage/invoices/<int:invoice_id>/",
        ManagerInvoiceDetailAPIView.as_view(),
        name="manager-invoice-detail",
    ),

    path(
        "manage/invoices/<int:invoice_id>/pdf/",
        ManagerInvoicePdfAPIView.as_view(),
        name="manager-invoice-pdf",
    ),

    path(
        "manage/invoices/<int:invoice_id>/cancel/",
        ManagerInvoiceCancelAPIView.as_view(),
        name="manager-invoice-cancel",
    ),

]