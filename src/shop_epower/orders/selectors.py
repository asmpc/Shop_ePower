from shop_epower.orders.models import Order, OrderStatus


def get_new_orders_count_for_manager():
    """
    Возвращает количество новых заказов.

    Используем для бейджа в navbar у manager/admin.
    """
    return Order.objects.filter(
        status=OrderStatus.NEW,
    ).count()