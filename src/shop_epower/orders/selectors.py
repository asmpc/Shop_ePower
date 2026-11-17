from decimal import Decimal

from django.db.models import (
    DecimalField,
    F,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce

from shop_epower.finance.models import AccountTransactionType
from shop_epower.orders.models import (
    Order,
    OrderFundApplication,
    OrderFundAssignment,
    OrderShipment,
    OrderStatus,
)
from shop_epower.payments.models import PaymentStatus


def get_new_orders_count_for_manager():
    """
    Возвращает количество новых заказов.

    Используем для бейджа в navbar у manager/admin.
    """
    return Order.objects.filter(
        status=OrderStatus.NEW,
    ).count()

def get_order_fund_assignments(*, order):
    """Возвращает историю назначений выбранного заказа."""
    return (
        OrderFundAssignment.objects
        .filter(order=order)
        .select_related(
            "account_transaction",
            "account_transaction__created_by",
            "account_transaction__reversal",
            "account_transaction__reversal__created_by",
        )
        .order_by("-created_at", "-pk")
    )

def get_unpaid_order_shipments_for_staff(
    *,
    customer_email="",
    order_id="",
):
    """Возвращает непогашенные отгрузки с поиском по email и номеру заказа."""

    customer_email = (customer_email or "").strip()

    applied_totals = (
        OrderFundApplication.objects.filter(
            shipment_id=OuterRef("pk"),
            account_transaction__reversal__isnull=True,
            assignment__account_transaction__reversal__isnull=True,
        )
        .order_by()
        .values("shipment_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    money_field = DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    shipments = (
        OrderShipment.objects.select_related(
            "order__user",
            "customer_account",
        )
        .annotate(
            applied_amount=Coalesce(
                Subquery(applied_totals),
                Decimal("0.00"),
                output_field=money_field,
            ),
        )
        .annotate(
            remaining_debt=F("total_amount") - F("applied_amount"),
        )
        .filter(
            remaining_debt__gt=Decimal("0.00"),
        )
        .order_by("-created_at", "-pk")
    )

    if customer_email:
        shipments = shipments.filter(
            order__user__email__icontains=customer_email,
        )

    order_id = str(order_id).strip() if order_id is not None else ""

    if order_id:
        try:
            order_number = int(order_id)
        except ValueError:
            return shipments.none()

        if not 1 <= order_number <= 2**63 - 1:
            return shipments.none()

        shipments = shipments.filter(
            order_id=order_number,
        )

    return shipments

def get_order_financial_summary(*, order):
    """Возвращает денежную сводку заказа со связанным финансовым счётом."""

    saved_order = (
        Order.objects.select_related("customer_account")
        .get(pk=order.pk)
    )

    if saved_order.customer_account_id is None:
        return None

    account = saved_order.customer_account

    received_amount = (
        saved_order.payments.filter(
            status=PaymentStatus.PAID,
            currency_snapshot=account.currency,
            deposit_transaction__account_id=account.pk,
            deposit_transaction__operation_type=AccountTransactionType.DEPOSIT,
            deposit_transaction__reversal__isnull=True,
        ).aggregate(
            total=Sum("amount"),
        )["total"]
        or Decimal("0.00")
    )

    assigned_amount = (
        saved_order.fund_assignments.filter(
            account_transaction__account_id=account.pk,
            account_transaction__reversal__isnull=True,
        ).aggregate(
            total=Sum("amount"),
        )["total"]
        or Decimal("0.00")
    )

    remaining_debt = (
        get_unpaid_order_shipments_for_staff(
            order_id=saved_order.pk,
        )
        .values_list("remaining_debt", flat=True)
        .first()
        or Decimal("0.00")
    )

    return {
        "received_amount": received_amount,
        "assigned_amount": assigned_amount,
        "remaining_debt": remaining_debt,
        "available_balance": account.available_balance,
        "currency": account.currency,
    }