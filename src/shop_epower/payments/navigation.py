from urllib.parse import urlsplit

from django.urls import reverse


def get_safe_manager_payment_list_url(candidate):
    list_url = reverse("payments:manager_payment_list")

    if not candidate:
        return list_url

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return list_url

    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or parsed.path != list_url
    ):
        return list_url

    return candidate