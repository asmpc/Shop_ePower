from urllib.parse import urlsplit

from django.urls import Resolver404, resolve, reverse


def _get_safe_return_url(candidate, *, default_url):
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
        or parsed.path != default_url
    ):
        return default_url

    return candidate


def get_safe_manager_account_list_url(candidate):
    return _get_safe_return_url(
        candidate,
        default_url=reverse("finance:manager_account_list"),
    )


def get_safe_manager_account_detail_url(candidate, *, account):
    return _get_safe_return_url(
        candidate,
        default_url=reverse(
            "finance:manager_account_detail",
            kwargs={"pk": account.pk},
        ),
    )

def get_safe_manager_account_return_url(candidate):
    """Проверяет адрес исходной карточки счёта для обратного перехода."""
    if not candidate:
        return None

    try:
        parsed = urlsplit(candidate)
        match = resolve(parsed.path)
    except (ValueError, Resolver404):
        return None

    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or match.view_name != "finance:manager_account_detail"
    ):
        return None

    return candidate
