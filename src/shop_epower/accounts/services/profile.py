

def _is_filled(value) -> bool:

    return bool(
        value
        and str(value).strip()
    )


def is_profile_complete(user) -> bool:

    required_user_fields = (
        user.first_name,
        user.last_name,
        user.email,
        user.phone,
    )

    if not all(
        _is_filled(value)
        for value in required_user_fields
    ):
        return False

    legal_profile = getattr(user, "legal_profile", None)

    if legal_profile is None:
        return True

    if not legal_profile.is_legal_entity:
        return True

    required_legal_fields = (
        legal_profile.company_name,
        legal_profile.tax_id,
        legal_profile.legal_address,
        legal_profile.bank_name,
        legal_profile.bank_account,
    )

    return all(
        _is_filled(value)
        for value in required_legal_fields
    )