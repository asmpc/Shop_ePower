from django.db.models import BigIntegerField, F, Value
from django.db.models.functions import Coalesce

from shop_epower.payments.models import (
    CustomerPayout,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PayoutMethod,
)


def get_money_movements_for_staff(
    *,
    account_id=None,
    customer_email=None,
    status=None,
    method=None,
    provider=None,
    order_id=None,
    transaction_id=None,
):
    customer_email = (customer_email or "").strip()
    status = (status or "").strip()
    method = (method or "").strip()
    provider = (provider or "").strip()
    transaction_id = (transaction_id or "").strip()

    fields = (
        "kind",
        "entry_id",
        "created_at",
        "amount",
        "performed_by",
        "account_id",
        "customer_email",
        "currency",
        "method",
        "status",
        "provider",
        "order_id",
        "transaction_id",
    )

    receipts = (
        Payment.objects.filter(
            status__in=(
                PaymentStatus.PAID,
                PaymentStatus.CANCELLED,
            ),
        )
        .order_by()
        .annotate(
            kind=Value("receipt"),
            entry_id=F("pk"),
            performed_by=Coalesce(
                F("deposit_transaction__created_by__username"),
                Value("Unknown"),
            ),
            account_id=Coalesce(
                F("deposit_transaction__account_id"),
                F("order__customer_account_id"),
            ),
            customer_email=Coalesce(
                F("deposit_transaction__account__user__email"),
                F("order__customer_email"),
                Value("Unknown"),
            ),
            currency=F("currency_snapshot"),
        )
        .values(*fields)
    )

    if (
        account_id is None
        and order_id is None
        and not customer_email
        and not status
        and not method
        and not provider
        and not transaction_id
    ):
        return receipts.none()

    if status not in (
        "",
        PaymentStatus.PAID,
        PaymentStatus.CANCELLED,
        "returned",
    ):
        return receipts.none()

    if method not in (
        "",
        PaymentMethod.ON_RECEIPT,
        PaymentMethod.INVOICE,
        PaymentMethod.ONLINE,
    ):
        return receipts.none()

    if provider not in (
        "",
        PaymentProvider.MANUAL,
        PaymentProvider.MOCK,
    ):
        return receipts.none()
    payouts = (
        CustomerPayout.objects.order_by()
        .annotate(
            kind=Value("payout"),
            status=Value("returned"),
            order_id=Value(
                None,
                output_field=BigIntegerField(),
            ),
            provider=Value(PaymentProvider.MANUAL),
            transaction_id=F("account_transaction__operation_key"),
            entry_id=F("pk"),
            performed_by=Coalesce(
                F("account_transaction__created_by__username"),
                Value("Unknown"),
            ),
            account_id=F("account_transaction__account_id"),
            customer_email=F(
                "account_transaction__account__user__email"
            ),
            currency=F("account_transaction__currency_snapshot"),
        )
        .values(*fields)
    )

    if account_id is not None:
        receipts = receipts.filter(account_id=account_id)
        payouts = payouts.filter(account_id=account_id)

    if order_id is not None:
        receipts = receipts.filter(order_id=order_id)
        payouts = payouts.none()

    if customer_email:
        receipts = receipts.filter(
            customer_email__iexact=customer_email,
        )
        payouts = payouts.filter(
            customer_email__iexact=customer_email,
        )

    if status:
        receipts = receipts.filter(status=status)
        payouts = payouts.filter(status=status)

    if method:
        receipts = receipts.filter(method=method)

        payout_method = {
            PaymentMethod.ON_RECEIPT: PayoutMethod.CASH,
            PaymentMethod.INVOICE: PayoutMethod.BANK_TRANSFER,
        }.get(method)

        if payout_method is None:
            payouts = payouts.none()
        else:
            payouts = payouts.filter(method=payout_method)

    if provider:
        receipts = receipts.filter(provider=provider)
        payouts = payouts.filter(provider=provider)

    if transaction_id:
        receipts = receipts.filter(transaction_id=transaction_id)
        payouts = payouts.filter(transaction_id=transaction_id)

    return receipts.union(
        payouts,
        all=True,
    ).order_by("-created_at", "kind", "-entry_id")