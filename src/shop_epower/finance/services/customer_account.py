from django.core.exceptions import ValidationError
from django.db import transaction

from shop_epower.finance.models import (
    CustomerAccount,
    CustomerAccountStatus,
    CustomerAccountStatusHistory,
    CustomerAccountType,
)


def create_personal_customer_account(
    *,
    user,
):
    if user.pk is None:
        raise ValidationError("User must be saved before creating a customer account.")

    account, _ = CustomerAccount.objects.get_or_create(
        user=user,
        account_type=CustomerAccountType.PERSONAL,
    )

    return account


def create_legal_customer_account(
    *,
    legal_profile,
):
    if legal_profile.pk is None:
        raise ValidationError(
            "Legal profile must be saved before creating a legal customer account."
        )

    if not legal_profile.is_legal_entity:
        raise ValidationError("Legal profile must be enabled for legal purchasing.")

    if not legal_profile.company_name.strip():
        raise ValidationError(
            "Company name is required to create a legal customer account."
        )

    if not legal_profile.tax_id.strip():
        raise ValidationError("Tax ID is required to create a legal customer account.")

    if not legal_profile.legal_address.strip():
        raise ValidationError(
            "Legal address is required to create a legal customer account."
        )

    account, _ = CustomerAccount.objects.get_or_create(
        user=legal_profile.user,
        account_type=CustomerAccountType.LEGAL,
        defaults={
            "legal_profile": legal_profile,
            "legal_tax_id_snapshot": legal_profile.tax_id,
        },
    )

    return account


@transaction.atomic
def change_customer_account_status(
    *,
    account,
    new_status,
    reason,
    changed_by=None,
):
    if account.pk is None:
        raise ValidationError(
            "Customer account must be saved before changing its status."
        )

    if new_status not in CustomerAccountStatus.values:
        raise ValidationError("Unsupported customer account status.")

    if not reason or not reason.strip():
        raise ValidationError("Status change reason is required.")

    locked_account = CustomerAccount.objects.select_for_update().get(pk=account.pk)

    if locked_account.status == new_status:
        raise ValidationError("Customer account already has the requested status.")

    old_status = locked_account.status

    locked_account.status = new_status
    locked_account.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    CustomerAccountStatusHistory.objects.create(
        account=locked_account,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        changed_by=changed_by,
    )

    return locked_account
