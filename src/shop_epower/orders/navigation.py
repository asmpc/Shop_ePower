from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse


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

    return redirect(
        f"{detail_url}?"
        f"{urlencode({'next': next_url})}"
    )