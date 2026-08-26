from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.payments.permissions import (
    IsAdmin,
    IsManagerOrAdmin,
)
from api.payments.serializers import (
    InvoiceDetailSerializer,
    ManagerInvoiceDetailSerializer,
    ManagerPaymentDetailSerializer,
    ManagerPaymentListSerializer,
    PaymentDetailSerializer,
    PaymentHistorySerializer,
    PaymentListSerializer,
)
from shop_epower.payments.models import Invoice, Payment
from shop_epower.payments.selectors.invoice import (
    get_invoice_for_user,
)
from shop_epower.payments.selectors.payment import (
    get_payment_for_user,
    get_payment_history,
    get_payment_history_for_user,
    get_payments_for_manager,
    get_payments_for_user,
)
from shop_epower.payments.services import (
    build_invoice_pdf_response,
    cancel_invoice,
    create_invoice_for_payment,
    mark_payment_cancelled,
    mark_payment_failed,
    mark_payment_paid,
    reset_payment_to_pending,
)


class ClientPaymentListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        payments = get_payments_for_user(
            request.user,
        )

        serializer = PaymentListSerializer(
            payments,
            many=True,
        )

        return Response(
            serializer.data,
        )


class ClientPaymentDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        payment_id,
    ):

        payment = get_payment_for_user(
            payment_id=payment_id,
            user=request.user,
        )

        serializer = PaymentDetailSerializer(
            payment,
        )

        return Response(
            serializer.data,
        )

class ClientPaymentHistoryAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        payment_id,
    ):

        history = get_payment_history_for_user(
            payment_id=payment_id,
            user=request.user,
        )

        serializer = PaymentHistorySerializer(
            history,
            many=True,
        )

        return Response(
            serializer.data,
        )

class ClientPaymentInvoiceAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        payment_id,
    ):

        invoice = get_invoice_for_user(
            payment_id=payment_id,
            user=request.user,
        )

        serializer = InvoiceDetailSerializer(
            invoice,
        )

        return Response(
            serializer.data,
        )

class ClientPaymentInvoicePDFAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        payment_id,
    ):

        invoice = get_invoice_for_user(
            payment_id=payment_id,
            user=request.user,
        )

        return build_invoice_pdf_response(
            invoice=invoice,
        )


class ManagerPaymentListAPIView(ListAPIView):
    """
    Список всех платежей для менеджеров и администраторов.
    """
    serializer_class = ManagerPaymentListSerializer

    permission_classes = (
        IsManagerOrAdmin,
    )

    def get_queryset(self):
        return get_payments_for_manager()


class ManagerPaymentDetailAPIView(RetrieveAPIView):
    """
        Детальная информация о платеже
        для менеджера и администратора.
        """
    serializer_class = ManagerPaymentDetailSerializer

    permission_classes = (
        IsManagerOrAdmin,
    )

    def get_queryset(self):
        return get_payments_for_manager()


class BaseManagerPaymentActionAPIView(APIView):

    permission_classes = (
        IsManagerOrAdmin,
    )

    queryset = Payment.objects.all()

    action_service = None

    def get_object(self):

        return get_object_or_404(
            self.queryset,
            pk=self.kwargs["pk"],
        )

    def post(self, request, pk):

        payment = self.get_object()

        payment = self.action_service(
            payment=payment,
            changed_by=request.user,
        )

        return Response(
            {
                "id": payment.pk,
                "status": payment.status,
            },
            status=status.HTTP_200_OK,
        )


class ManagerPaymentMarkPaidAPIView(
    BaseManagerPaymentActionAPIView,
):

    action_service = staticmethod(
        mark_payment_paid,
    )


class ManagerPaymentMarkFailedAPIView(
    BaseManagerPaymentActionAPIView,
):

    action_service = staticmethod(
        mark_payment_failed,
    )


class ManagerPaymentMarkCancelledAPIView(
    BaseManagerPaymentActionAPIView,
):

    action_service = staticmethod(
        mark_payment_cancelled,
    )


class ManagerPaymentResetToPendingAPIView(APIView):

    permission_classes = (
        IsAdmin,
    )

    queryset = Payment.objects.all()

    def get_object(self):

        return get_object_or_404(
            self.queryset,
            pk=self.kwargs["pk"],
        )

    def post(
            self,
            request,
            pk,
    ):

        payment = self.get_object()

        try:
            payment = reset_payment_to_pending(
                payment=payment,
                comment=request.data.get(
                    "comment",
                    "",
                ),
                changed_by=request.user,
            )


        except DjangoValidationError as exc:

            raise DRFValidationError(

                {

                    "detail": exc.messages[0],

                }

            ) from exc

        return Response(
            {
                "id": payment.pk,
                "status": payment.status,
            },
            status=status.HTTP_200_OK,
        )


class ManagerPaymentHistoryAPIView(
    ListAPIView,
):

    permission_classes = (
        IsManagerOrAdmin,
    )

    serializer_class = PaymentHistorySerializer

    def get_queryset(self):
        payment = get_object_or_404(
            Payment,
            pk=self.kwargs["pk"],
        )

        return get_payment_history(
            payment=payment,
        )

class ManagerInvoiceCreateAPIView(APIView):

    permission_classes = (
        IsManagerOrAdmin,
    )

    def post(
        self,
        request,
        payment_id,
    ):

        payment = get_object_or_404(
            Payment.objects.select_related(
                "order",
                "order__user",
            ),
            pk=payment_id,
        )

        try:
            invoice = create_invoice_for_payment(
                payment=payment,
            )



        except DjangoValidationError as exc:

            raise DRFValidationError(

                {

                    "detail": exc.messages[0],

                }

            ) from exc

        return Response(

            {

                "id": invoice.pk,

                "invoice_number": invoice.invoice_number,

            },

            status=status.HTTP_201_CREATED,

        )

class ManagerInvoiceDetailAPIView(APIView):

    permission_classes = (
        IsManagerOrAdmin,
    )

    def get(
        self,
        request,
        invoice_id,
    ):
        invoice = get_object_or_404(
            Invoice,
            pk=invoice_id,
        )

        serializer = ManagerInvoiceDetailSerializer(
            invoice,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

class ManagerInvoicePdfAPIView(APIView):

    permission_classes = (
        IsManagerOrAdmin,
    )

    def get(
        self,
        request,
        invoice_id,
    ):

        invoice = get_object_or_404(
            Invoice,
            pk=invoice_id,
        )

        return build_invoice_pdf_response(
            invoice=invoice,
        )


class ManagerInvoiceCancelAPIView(APIView):

    permission_classes = (
        IsAdmin,
    )

    def post(self, request, invoice_id):

        invoice = get_object_or_404(
            Invoice,
            pk=invoice_id,
        )

        try:
            cancel_invoice(
                invoice=invoice,
                cancelled_by=request.user,
                comment=request.data.get(
                    "comment",
                    "",
                ),
            )


        except DjangoValidationError as exc:

            raise DRFValidationError(

                {

                    "detail": exc.messages[0],

                }

            ) from exc

        return Response(
            status=status.HTTP_200_OK,
        )