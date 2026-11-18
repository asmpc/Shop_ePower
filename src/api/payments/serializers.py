from decimal import Decimal

from rest_framework import serializers

from shop_epower.payments.models import (
    CustomerPayout,
    Invoice,
    Payment,
    PaymentHistory,
    PaymentMethod,
    PayoutMethod,
)


class PaymentListSerializer(serializers.ModelSerializer):
    customer_account_id = serializers.SerializerMethodField()

    def get_customer_account_id(self, payment):
        if payment.deposit_transaction_id is not None:
            return payment.deposit_transaction.account_id

        if payment.order_id is not None:
            return payment.order.customer_account_id

        return None

    class Meta:
        model = Payment

        fields = (
            "id",
            "order_id",
            "customer_account_id",
            "method",
            "status",
            "provider",
            "amount",
            "currency_snapshot",
            "transaction_id",
            "created_at",
        )


class PaymentDetailSerializer(PaymentListSerializer):
    pass


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


class ManagerPaymentDetailSerializer(PaymentListSerializer):
    customer_email = serializers.SerializerMethodField()

    def get_customer_email(self, payment):
        if payment.deposit_transaction_id is not None:
            return payment.deposit_transaction.account.user.email

        if payment.order_id is not None:
            return payment.order.customer_email

        return None

    class Meta:
        model = Payment

        fields = (
            "id",
            "order",
            "customer_account_id",
            "customer_email",
            "method",
            "provider",
            "status",
            "amount",
            "currency_snapshot",
        )


class ManagerPaymentListSerializer(ManagerPaymentDetailSerializer):
    class Meta(ManagerPaymentDetailSerializer.Meta):
        fields = (
            *ManagerPaymentDetailSerializer.Meta.fields,
            "created_at",
        )

class PaymentHistorySerializer(
    serializers.ModelSerializer,
):
    changed_by = serializers.StringRelatedField()

    class Meta:
        model = PaymentHistory

        fields = (
            "old_status",
            "new_status",
            "comment",
            "changed_by",
            "created_at",
        )


class ManagerInvoiceDetailSerializer(
    serializers.ModelSerializer,
):
    class Meta:
        model = Invoice

        fields = (
            "id",
            "invoice_number",
            "amount",
            "currency_snapshot",

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

            "created_at",
        )


class ManualPaymentReceiptSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    method = serializers.ChoiceField(
        choices=(
            PaymentMethod.ON_RECEIPT,
            PaymentMethod.INVOICE,
        ),
    )
    operation_key = serializers.CharField(
        max_length=255,
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class ManualReceiptCancellationSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=True,
        allow_blank=False,
    )
    operation_key = serializers.CharField(
        max_length=255,
    )


class ManualAccountPayoutSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    method = serializers.ChoiceField(
        choices=PayoutMethod.choices,
    )
    comment = serializers.CharField(
        required=True,
        allow_blank=False,
    )
    operation_key = serializers.CharField(
        max_length=255,
    )


class ManagerCustomerPayoutSerializer(serializers.ModelSerializer):
    customer_account_id = serializers.IntegerField(
        source="account_transaction.account_id",
        read_only=True,
    )
    currency_snapshot = serializers.CharField(
        source="account_transaction.currency_snapshot",
        read_only=True,
    )
    performed_by = serializers.CharField(
        source="account_transaction.created_by.username",
        read_only=True,
    )
    comment = serializers.CharField(
        source="account_transaction.comment",
        read_only=True,
    )
    operation_key = serializers.CharField(
        source="account_transaction.operation_key",
        read_only=True,
    )
    status = serializers.SerializerMethodField()

    def get_status(self, _payout):
        return "returned"

    class Meta:
        model = CustomerPayout
        fields = (
            "id",
            "customer_account_id",
            "amount",
            "method",
            "status",
            "currency_snapshot",
            "performed_by",
            "comment",
            "operation_key",
            "created_at",
        )
        read_only_fields = fields