from django.core.mail import send_mail
from django.conf import settings
from shop_epower.orders.models import Order
from django.contrib.auth import get_user_model

User = get_user_model()


def send_order_created_email_to_customer(order: Order):
    """
    Отправка письма клиенту при создании заказа.
    """
    subject = f"Your Order #{order.id} has been created"
    message = f"Hello {order.customer_name},\n\nYour order #{order.id} has been successfully created.\nTotal: {order.total_price}.\nThank you for shopping with us!"
    recipient = [order.customer_email]

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient,
        fail_silently=False,
    )


def send_order_created_notification_to_managers(order: Order):
    """
    Отправка уведомления всем менеджерам о новом заказе.
    """
    subject = f"New Order #{order.id} Created"
    message = f"Order #{order.id} has been created by {order.customer_name} ({order.customer_email}). Total: {order.total_price}."

    managers = User.objects.filter(is_staff=True)
    recipient_list = [m.email for m in managers if m.email]

    if recipient_list:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )