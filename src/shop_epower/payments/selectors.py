from shop_epower.payments.models import Payment


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