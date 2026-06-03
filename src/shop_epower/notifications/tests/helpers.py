from decimal import Decimal

from django.contrib.auth import get_user_model

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import Order

User = get_user_model()


def create_test_user(
    email="client@test.com",
    username="client",
    role="client",
    is_staff=False,
):
    return User.objects.create_user(
        email=email,
        username=username,
        password="12345678",
        role=role,
        is_staff=is_staff,
    )


def create_test_order(
    *,
    user,
    total_price=Decimal("100.00"),
):
    return Order.objects.create(
        user=user,
        is_legal_entity=False,
        customer_name=user.get_full_name() or user.username,
        customer_email=user.email,
        customer_phone=getattr(user, "phone", ""),
        company_name="",
        tax_id="",
        legal_address="",
        bank_name="",
        bank_account="",
        total_price=total_price,
        currency_snapshot=get_base_currency(),
        delivery_method="pickup",
        delivery_provider="",
        delivery_address="",
        delivery_comment="",
    )