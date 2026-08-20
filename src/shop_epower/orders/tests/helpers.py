from decimal import Decimal

from shop_epower.core.currency import get_base_currency
from shop_epower.orders.models import Order, OrderStatus



def create_test_order(
    *,
    user,
    total_price=Decimal("100.00"),
    status=OrderStatus.NEW,
    **kwargs,
):
    return Order.objects.create(
        user=user,
        status=status,
        total_price=total_price,
        is_legal_entity=False,
        customer_name=user.get_full_name() or user.username,
        customer_email=user.email,
        customer_phone=getattr(user, "phone", ""),
        company_name="",
        tax_id="",
        legal_address="",
        bank_name="",
        bank_account="",
        currency_snapshot=get_base_currency(),
        delivery_method="pickup",
        delivery_provider="",
        delivery_address="",
        delivery_comment="",
        **kwargs,
    )