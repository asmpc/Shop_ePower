from django.urls import path

from api.payments.views import (
    ClientInvoiceDetailAPIView,
    ClientInvoicePDFAPIView,
    ClientPaymentDetailAPIView,
    ClientPaymentHistoryAPIView,
    ClientPaymentListAPIView,
    ManagerInvoiceCancelAPIView,
    ManagerInvoiceCreateAPIView,
    ManagerInvoiceDetailAPIView,
    ManagerInvoicePdfAPIView,
    ManagerPaymentDetailAPIView,
    ManagerPaymentHistoryAPIView,
    ManagerPaymentListAPIView,
    ManagerPaymentMarkCancelledAPIView,
    ManagerPaymentMarkPaidAPIView,
    ManagerPaymentResetToPendingAPIView,
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
        "my/invoices/<int:invoice_id>/",
        ClientInvoiceDetailAPIView.as_view(),
        name="client-invoice-detail",
    ),

    path(
        "my/invoices/<int:invoice_id>/pdf/",
        ClientInvoicePDFAPIView.as_view(),
        name="client-invoice-pdf",
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
        "manage/orders/<int:order_id>/invoice/",
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