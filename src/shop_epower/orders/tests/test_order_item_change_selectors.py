from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import (
    OrderItemChange,
    OrderStatus,
)
from shop_epower.orders.selectors import get_order_item_changes
from shop_epower.orders.tests.helpers import (
    create_test_order,
    create_test_order_item_change,
)


class TestsOrderItemChangeSelectors(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("200.00"),
        )
        self.other_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("200.00"),
        )

    def _create_change(
        self,
        *,
        old_quantity,
        new_quantity,
        order=None,
        item_id=101,
    ):
        return create_test_order_item_change(
            order=self.order if order is None else order,
            changed_by=self.manager,
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            order_item_id_snapshot=item_id,
        )

    # История содержит только записи выбранного заказа.
    # Сортировка: дата по убыванию, затем pk по убыванию.
    # Записи вместе с авторами загружаются одним SQL-запросом.
    def test_returns_order_changes_newest_first_with_authors(self):
        first_tied = self._create_change(
            old_quantity=4,
            new_quantity=3,
        )
        last_tied = self._create_change(
            old_quantity=3,
            new_quantity=2,
        )
        older = self._create_change(
            old_quantity=5,
            new_quantity=4,
        )
        self._create_change(
            order=self.other_order,
            item_id=202,
            old_quantity=3,
            new_quantity=2,
        )

        recorded_at = timezone.now()

        OrderItemChange.objects.filter(order=self.order).update(
            created_at=recorded_at,
        )
        OrderItemChange.objects.filter(pk=older.pk).update(
            created_at=recorded_at - timedelta(days=1),
        )

        with self.assertNumQueries(1):
            changes = list(get_order_item_changes(order=self.order))
            authors = [
                change.changed_by.username
                for change in changes
            ]

        self.assertEqual(
            [change.pk for change in changes],
            [last_tied.pk, first_tied.pk, older.pk],
        )
        self.assertEqual(authors, [self.manager.username] * 3)
