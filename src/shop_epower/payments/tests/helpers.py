from decimal import Decimal

from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
)


def create_payment(
    *,
    order,
    method=PaymentMethod.INVOICE,
    amount=Decimal("100.00"),
    **kwargs,
):
    return Payment.objects.create(
        order=order,
        method=method,
        amount=amount,
        **kwargs,
    )