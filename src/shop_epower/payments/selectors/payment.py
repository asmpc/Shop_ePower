from shop_epower.payments.models import Payment
from django.shortcuts import get_object_or_404


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
):
    queryset = (
        Payment.objects
        .select_related(
            "order",
            "order__user",
        )
        .order_by("-created_at")
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