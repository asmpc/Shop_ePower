from urllib.parse import urlencode, urlsplit

from django.shortcuts import redirect
from django.urls import reverse


def get_safe_manager_order_return_url(candidate):
    default_url = reverse("orders:manager_order_list")
    allowed_paths = {
        default_url,
        reverse("payments:manager_payment_list"),
    }

    if not candidate:
        return default_url

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return default_url

    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or parsed.path not in allowed_paths
    ):
        return default_url

    return candidate


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
