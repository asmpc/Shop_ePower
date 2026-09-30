from django.core.exceptions import ValidationError
from django.db import transaction

from shop_epower.accounts.models import LegalProfile
from shop_epower.finance.models import CustomerAccount, CustomerAccountType
from shop_epower.finance.services import (
    correct_legal_account_tax_id,
    create_legal_customer_account,
)


@transaction.atomic
def save_legal_profile(*, user, data):
    profile, _ = LegalProfile.objects.select_for_update().get_or_create(user=user)

    if data.get("is_legal_entity") is False:
        data = {"is_legal_entity": False}

    requested_tax_id = data.get("tax_id", profile.tax_id)

    if requested_tax_id != profile.tax_id:
        legal_account = (
            CustomerAccount.objects.select_for_update()
            .filter(user=user, account_type=CustomerAccountType.LEGAL)
            .first()
        )

        if legal_account is not None and legal_account.transactions.exists():
            raise ValidationError(
                "Legal tax ID cannot be changed after financial activity."
            )

    allowed_fields = (
        "is_legal_entity",
        "company_name",
        "tax_id",
        "legal_address",
        "bank_name",
        "bank_account",
    )

    for field in allowed_fields:
        if field in data:
            setattr(profile, field, data[field])

    profile.save()

    if profile.is_legal_entity:
        account = create_legal_customer_account(legal_profile=profile)

        if account.legal_tax_id_snapshot != profile.tax_id:
            correct_legal_account_tax_id(legal_profile=profile)

    return profile
