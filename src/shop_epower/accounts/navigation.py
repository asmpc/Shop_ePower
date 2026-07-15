from urllib.parse import urlencode

from django.urls import reverse


def get_profile_edit_url(*, next_url=None):

    profile_url = reverse(
        "accounts:profile_edit",
    )

    if not next_url:
        return profile_url

    return (
        f"{profile_url}?"
        f"{urlencode({'next': next_url})}"
    )