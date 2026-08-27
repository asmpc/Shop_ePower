from celery import shared_task

from shop_epower.notifications.services import (
    send_order_created_email_to_customer,
    send_order_created_notification_to_managers,
)
from shop_epower.orders.models import Order


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={
        "max_retries": 3,
    },
    acks_late=True,
)
def send_customer_order_created_email(order_id):

    order = Order.objects.get(
        pk=order_id,
    )

    send_order_created_email_to_customer(
        order,
    )


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={
        "max_retries": 3,
    },
    acks_late=True,
)
def notify_managers_about_new_order(order_id):

    order = Order.objects.get(
        pk=order_id,
    )

    send_order_created_notification_to_managers(
        order,
    )