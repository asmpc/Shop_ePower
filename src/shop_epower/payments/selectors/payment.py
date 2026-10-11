from django.shortcuts import get_object_or_404

from shop_epower.payments.models import Payment


def get_payments_for_user(user):

    return (
        Payment.objects
        .filter(
            order__user=user,
        )
        .select_related(
            "order",
        )
        .order_by(
            "-created_at",
        )
    )


def get_payment_for_user(
    *,
    payment_id,
    user,
):

    return get_object_or_404(
        get_payments_for_user(
            user,
        ),
        id=payment_id,
    )


def get_payments_for_manager(
    *,
    status=None,
    method=None,
    provider=None,
    order_id=None,
    transaction_id=None,
    customer_email=None,
):
    queryset = (
        Payment.objects
        .select_related(
            "order",
            "order__user",
        )
        .order_by("-created_at", "-pk")
    )

    if status:
        queryset = queryset.filter(
            status=status,
        )

    if method:
        queryset = queryset.filter(
            method=method,
        )

    if provider:
        queryset = queryset.filter(
            provider=provider,
        )

    if order_id is not None:
        queryset = queryset.filter(order_id=order_id)

    if transaction_id is not None:
        queryset = queryset.filter(transaction_id=transaction_id)

    if customer_email is not None:
        queryset = queryset.filter(
            order__customer_email__iexact=customer_email,
        )

    return queryset

def get_payment_history(
    *,
    payment,
):

    return (
        payment.history
        .select_related(
            "changed_by",
        )
        .order_by(
            "-created_at",
        )
    )

def get_payment_history_for_user(
    *,
    payment_id,
    user,
):

    payment = get_payment_for_user(
        payment_id=payment_id,
        user=user,
    )

    return get_payment_history(
        payment=payment,
    )

def get_manager_payments_queryset():
    """
    Возвращает queryset платежей
    для Manager/Admin API.
    """

    return (
        Payment.objects
        .select_related(
            "order",
            "order__user",
        )
    )