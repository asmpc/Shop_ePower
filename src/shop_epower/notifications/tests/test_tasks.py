from unittest.mock import patch

from django.test import TestCase

from shop_epower.notifications.tasks import (
    notify_managers_about_new_order,
    send_customer_order_created_email,
)


class TestsNotificationTasks(TestCase):

    # Проверяем, что задача получает заказ по id
    # и запускает сервис отправки письма клиенту.
    @patch(
        "shop_epower.notifications.tasks."
        "send_order_created_email_to_customer"
    )
    @patch(
        "shop_epower.notifications.tasks."
        "Order.objects.get"
    )
    def test_send_customer_order_created_email(
        self,
        mocked_order_get,
        mocked_send_email,
    ):

        order = object()

        mocked_order_get.return_value = order

        send_customer_order_created_email(
            order_id=1,
        )

        mocked_order_get.assert_called_once_with(
            pk=1,
        )

        mocked_send_email.assert_called_once_with(
            order,
        )

    # Проверяем, что задача получает заказ по id
    # и запускает сервис уведомления менеджеров.
    @patch(
        "shop_epower.notifications.tasks."
        "send_order_created_notification_to_managers"
    )
    @patch(
        "shop_epower.notifications.tasks."
        "Order.objects.get"
    )
    def test_notify_managers_about_new_order(
        self,
        mocked_order_get,
        mocked_notify_managers,
    ):

        order = object()

        mocked_order_get.return_value = order

        notify_managers_about_new_order(
            order_id=1,
        )

        mocked_order_get.assert_called_once_with(
            pk=1,
        )

        mocked_notify_managers.assert_called_once_with(
            order,
        )