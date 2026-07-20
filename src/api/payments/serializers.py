from rest_framework import serializers

from shop_epower.payments.models import (
    Invoice,
    Payment,
    PaymentHistory,
)



class PaymentListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Payment
        fields = (
            'id',
            'order_id',
            'method',
            'status',
            'provider',
            'amount',
            'currency_snapshot',
            'transaction_id',
            'created_at',
        )


class PaymentDetailSerializer(
    serializers.ModelSerializer,
):

    class Meta:
        model = Payment

        fields = (
            'id',
            'order_id',
            'method',
            'status',
            'provider',
            'amount',
            'currency_snapshot',
            'transaction_id',
            'created_at',
        )


class PaymentHistorySerializer(
    serializers.ModelSerializer,
):

    class Meta:
        model = PaymentHistory

        fields = (
            'id',
            'old_status',
            'new_status',
            'comment',
            'changed_by',
            'created_at',
        )


class InvoiceDetailSerializer(
    serializers.ModelSerializer,
):

    class Meta:
        model = Invoice

        fields = (
            "id",
            "order_id",
            "payment_id",
            "invoice_number",
            "status",
            "seller_company_name",
            "seller_short_company_name",
            "seller_tax_id",
            "seller_tax_registration_reason_code",
            "seller_state_registration_number",
            "seller_legal_address",
            "seller_actual_address",
            "seller_bank_name",
            "seller_bank_account",
            "seller_bank_code",
            "seller_correspondent_account",
            "seller_phone",
            "seller_email",
            "buyer_name",
            "buyer_email",
            "buyer_phone",
            "buyer_address",
            "buyer_is_legal_entity",
            "buyer_company_name",
            "buyer_tax_id",
            "buyer_legal_address",
            "buyer_bank_name",
            "buyer_bank_account",
            "amount",
            "currency_snapshot",
            "cancel_comment",
            "cancelled_at",
            "cancelled_by",
            "created_at",
            "updated_at",
        )


class ManagerPaymentListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Payment

        fields = (
            "id",
            "order",
            "method",
            "provider",
            "status",
            "amount",
            "currency_snapshot",
            "created_at",
        )


class ManagerPaymentDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = Payment

        fields = (
            "id",
            "order",
            "method",
            "provider",
            "status",
            "amount",
            "currency_snapshot",
        )


