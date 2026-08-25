from django.test import TestCase

from rest_framework.test import APIClient

from shop_epower.orders.tests.helpers import (
    create_test_order,
)

from shop_epower.accounts.tests.helpers import (
    create_test_user,
)

from shop_epower.payments.models import (
    PaymentStatus,
)
from shop_epower.payments.services import (
    mark_payment_paid,
)
from shop_epower.payments.tests.helpers import (
    create_test_payment,
)


class TestsClientPaymentHistoryAPI(TestCase):

    def setUp(self):

        self.client = APIClient()

        self.user = create_test_user(
            email='payment-history-client@test.com',
            username='payment-history-client',
        )

        self.order = create_test_order(
            user=self.user,
        )

        self.payment = create_test_payment(
            order=self.order,
        )

    # Проверяем, что клиент может получить
    # историю собственного платежа.
    def test_client_can_get_own_payment_history(self):

        mark_payment_paid(
            payment=self.payment,
            manager_comment='Payment confirmed',
            changed_by=self.user,
        )

        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            f'/api/payments/my/{self.payment.id}/history/',
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        history_item = response.data[0]

        self.assertEqual(
            history_item['old_status'],
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            history_item['new_status'],
            PaymentStatus.PAID,
        )

        self.assertEqual(
            history_item['comment'],
            'Payment confirmed',
        )