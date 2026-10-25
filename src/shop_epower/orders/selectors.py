from shop_epower.orders.models import (
    Order,
    OrderFundAssignment,
    OrderStatus,
)


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