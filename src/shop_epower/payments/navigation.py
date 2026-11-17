from urllib.parse import urlsplit

from django.urls import reverse


def get_safe_manager_payment_return_url(candidate, *, payment):
    list_url = reverse("payments:manager_payment_list")

    if not candidate:
        return list_url

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return list_url

    if parsed.scheme or parsed.netloc or parsed.fragment:
        return list_url

    allowed_paths = {list_url}

    if payment.order_id is not None:
        allowed_paths.add(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": payment.order_id},
            ),
        )

    if parsed.path not in allowed_paths:
        return list_url

    return candidate

def get_safe_manager_payment_detail_url(candidate, *, payment):
    detail_url = reverse(
        "payments:manager_payment_detail",
        kwargs={"pk": payment.pk},
    )

    if not candidate:
        return detail_url

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return detail_url

    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or parsed.path != detail_url
    ):
        return detail_url

    return candidate