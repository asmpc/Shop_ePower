from urllib.parse import urlencode, urlsplit

from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse


def get_safe_manager_order_return_url(
    candidate,
    *,
    payment_ids=(),
    order=None,
):
    default_url = reverse("orders:manager_order_list")

    if not candidate:
        return default_url

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return default_url

    if parsed.scheme or parsed.netloc or parsed.fragment:
        return default_url

    allowed_paths = {
        default_url,
        reverse("orders:manager_unpaid_order_list"),
        reverse("payments:manager_payment_list"),
    }

    if parsed.path in allowed_paths:
        return candidate

    if order is not None:
        try:
            match = resolve(parsed.path)
        except Resolver404:
            return default_url

        if match.view_name != "payments:manager_payment_detail":
            return default_url

        payment_id = match.kwargs["pk"]

        if not 1 <= payment_id <= 2**63 - 1:
            return default_url

        if order.payments.filter(pk=payment_id).exists():
            return candidate

        return default_url

    for payment_id in payment_ids:
        if parsed.path == reverse(
            "payments:manager_payment_detail",
            args=[payment_id],
        ):
            return candidate

    return default_url


def redirect_to_manager_order_detail(
    *,
    request,
    order_id,
):
    """
    Redirects back to manager order detail
    while preserving the original manager list URL.
    """

    detail_url = reverse(
        "orders:manager_order_detail",
        args=[order_id],
    )

    next_url = request.POST.get(
        "next",
        reverse(
            "orders:manager_order_list",
        ),
    )

    return redirect(f"{detail_url}?{urlencode({'next': next_url})}")
