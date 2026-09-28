from django.db import transaction

from shop_epower.accounts.models import User
from shop_epower.finance.services import create_personal_customer_account


@transaction.atomic
def register_customer(*, email, username, password):
    user = User.objects.create_user(
        email=email,
        username=username,
        password=password,
    )
    create_personal_customer_account(user=user)
    return user
