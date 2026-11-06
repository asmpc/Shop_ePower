from decimal import Decimal

from django.db.models import (
    DecimalField,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce

from shop_epower.finance.selectors.accounts import get_customer_accounts
from shop_epower.orders.models import (
    OrderFundApplication,
    OrderFundAssignment,
)


def get_customer_account_balances(
    *,
    user,
):
    assignment_totals = (
        OrderFundAssignment.objects.filter(
            order__customer_account_id=OuterRef("pk"),
            account_transaction__reversal__isnull=True,
        )
        .order_by()
        .values("order__customer_account_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    application_totals = (
        OrderFundApplication.objects.filter(
            assignment__order__customer_account_id=OuterRef("pk"),
            assignment__account_transaction__reversal__isnull=True,
            account_transaction__reversal__isnull=True,
        )
        .order_by()
        .values("assignment__order__customer_account_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    money_field = DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    assigned_amount = Coalesce(
        Subquery(assignment_totals),
        Decimal("0.00"),
        output_field=money_field,
    )
    applied_amount = Coalesce(
        Subquery(application_totals),
        Decimal("0.00"),
        output_field=money_field,
    )

    return get_customer_accounts(
        user=user,
    ).annotate(
        assigned_prepayment=assigned_amount - applied_amount,
    )