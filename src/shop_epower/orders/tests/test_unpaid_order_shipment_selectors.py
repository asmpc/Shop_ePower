from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderItem, OrderStatus
from shop_epower.orders.selectors import get_unpaid_order_shipments_for_staff
from shop_epower.orders.services import (
    assign_order_funds,
    cancel_order_fund_assignment,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import PaymentMethod
from shop_epower.payments.services import record_manual_order_payment


class TestsUnpaidOrderShipmentSelectors(TestCase):
    def setUp(self):
        self.user = create_test_user(
            email="debtor-alice@example.com",
        )
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )

        self.product = create_test_product()
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

    def _create_prepayment_assignment(self, *, amount):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="unpaid:selector:receipt",
            created_by=self.manager,
        )
        return assign_order_funds(
            order=self.order,
            amount=amount,
            operation_key="unpaid:selector:assignment",
            created_by=self.manager,
        )

    # Частично погашенная отгрузка остаётся в списке долгов.
    # Остаток рассчитывается по применённым к ней средствам.
    def test_partially_paid_shipment_has_remaining_debt(self):
        self._create_prepayment_assignment(
            amount=Decimal("60.00"),
        )

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        shipments = list(
            get_unpaid_order_shipments_for_staff()
        )

        self.assertEqual(len(shipments), 1)

        unpaid_shipment = shipments[0]

        self.assertEqual(unpaid_shipment.pk, shipment.pk)
        self.assertEqual(unpaid_shipment.order_id, self.order.pk)
        self.assertEqual(
            unpaid_shipment.applied_amount,
            Decimal("60.00"),
        )
        self.assertEqual(
            unpaid_shipment.remaining_debt,
            Decimal("40.00"),
        )

    # Отгрузка без погашений попадает в список с полным долгом.
    # Отсутствие применений считается нулевой погашенной суммой.
    def test_shipment_without_payments_has_full_debt(self):
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        shipments = list(
            get_unpaid_order_shipments_for_staff()
        )

        self.assertEqual(len(shipments), 1)

        unpaid_shipment = shipments[0]

        self.assertEqual(unpaid_shipment.pk, shipment.pk)
        self.assertEqual(
            unpaid_shipment.applied_amount,
            Decimal("0.00"),
        )
        self.assertEqual(
            unpaid_shipment.remaining_debt,
            Decimal("100.00"),
        )

    # Полностью погашенная отгрузка отсутствует в списке долгов.
    # Заказ сохраняет статус COMPLETED.
    def test_fully_paid_shipment_is_excluded(self):
        self._create_prepayment_assignment(
            amount=Decimal("100.00"),
        )
        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        shipments = list(
            get_unpaid_order_shipments_for_staff()
        )

        self.assertEqual(shipments, [])

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            OrderStatus.COMPLETED,
        )

    # После отмены полного погашения отгрузка возвращается в список.
    # Отменённое применение больше не уменьшает её долг.
    def test_cancelled_assignment_restores_shipment_debt(self):
        assignment = self._create_prepayment_assignment(
            amount=Decimal("100.00"),
        )
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.assertEqual(
            list(get_unpaid_order_shipments_for_staff()),
            [],
        )

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="unpaid:selector:cancel-assignment",
            created_by=self.manager,
            comment="Assignment entered by mistake.",
        )

        shipments = list(
            get_unpaid_order_shipments_for_staff()
        )

        self.assertEqual(len(shipments), 1)

        unpaid_shipment = shipments[0]

        self.assertEqual(unpaid_shipment.pk, shipment.pk)
        self.assertEqual(
            unpaid_shipment.applied_amount,
            Decimal("0.00"),
        )
        self.assertEqual(
            unpaid_shipment.remaining_debt,
            Decimal("100.00"),
        )

    # Долг каждой отгрузки рассчитывается отдельно,
    # даже если заказы используют один финансовый счёт.
    def test_debt_is_calculated_separately_for_each_shipment(self):
        self._create_prepayment_assignment(
            amount=Decimal("60.00"),
        )
        first_shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        second_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("200.00"),
        )
        OrderItem.objects.create(
            order=second_order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("200.00"),
            quantity=1,
            total_price=Decimal("200.00"),
            currency_snapshot=second_order.currency_snapshot,
        )
        second_shipment = complete_order_shipment(
            order=second_order,
            created_by=self.manager,
        )

        shipments = {
            shipment.pk: shipment
            for shipment in get_unpaid_order_shipments_for_staff()
        }

        self.assertEqual(len(shipments), 2)

        first = shipments[first_shipment.pk]
        second = shipments[second_shipment.pk]

        self.assertEqual(first.applied_amount, Decimal("60.00"))
        self.assertEqual(first.remaining_debt, Decimal("40.00"))
        self.assertEqual(second.applied_amount, Decimal("0.00"))
        self.assertEqual(second.remaining_debt, Decimal("200.00"))

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.debt_balance,
            Decimal("240.00"),
        )

    # Несколько погашений суммируются в пределах одной отгрузки.
    # Отмена одного назначения сохраняет другое погашение.
    def test_cancelling_one_assignment_preserves_other_settlement(self):
        first_assignment = self._create_prepayment_assignment(
            amount=Decimal("30.00"),
        )
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        assign_order_funds(
            order=self.order,
            amount=Decimal("20.00"),
            operation_key="unpaid:selector:second-assignment",
            created_by=self.manager,
        )

        before = get_unpaid_order_shipments_for_staff().get(
            pk=shipment.pk,
        )

        self.assertEqual(before.applied_amount, Decimal("50.00"))
        self.assertEqual(before.remaining_debt, Decimal("50.00"))

        cancel_order_fund_assignment(
            assignment=first_assignment,
            operation_key="unpaid:selector:cancel-first-assignment",
            created_by=self.manager,
            comment="First assignment entered by mistake.",
        )

        after = get_unpaid_order_shipments_for_staff().get(
            pk=shipment.pk,
        )

        self.assertEqual(after.applied_amount, Decimal("20.00"))
        self.assertEqual(after.remaining_debt, Decimal("80.00"))

    # Старый завершённый заказ без записи отгрузки
    # не попадает в список и не получает финансовые операции.
    def test_completed_order_without_shipment_is_excluded(self):
        self.order.status = OrderStatus.COMPLETED
        self.order.save(update_fields=["status"])

        shipments = list(
            get_unpaid_order_shipments_for_staff()
        )

        self.assertEqual(shipments, [])
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.account.transactions.exists())

    # Список получает отгрузку, заказ, клиента и счёт одним запросом.
    # Обращение к связанным объектам не создаёт дополнительных запросов.
    def test_unpaid_shipments_and_related_data_use_one_query(self):
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        with self.assertNumQueries(1):
            shipments = list(
                get_unpaid_order_shipments_for_staff()
            )

            self.assertEqual(len(shipments), 1)

            result = shipments[0]

            self.assertEqual(result.pk, shipment.pk)
            self.assertEqual(
                result.order.user.email,
                self.user.email,
            )
            self.assertEqual(
                result.customer_account.currency,
                self.account.currency,
            )
            self.assertEqual(
                result.remaining_debt,
                Decimal("100.00"),
            )

    # Поиск по фрагменту email выбирает отгрузки нужного клиента.
    # Отгрузки другого клиента исключаются из результата.
    def test_finds_unpaid_shipments_by_customer_email(self):
        matching_shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        other_user = create_test_user(
            email="debtor-bob@example.com",
        )
        other_account = create_personal_customer_account(
            user=other_user,
        )
        other_order = create_test_order(
            user=other_user,
            customer_account=other_account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )
        OrderItem.objects.create(
            order=other_order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=other_order.currency_snapshot,
        )
        complete_order_shipment(
            order=other_order,
            created_by=self.manager,
        )

        shipments = list(
            get_unpaid_order_shipments_for_staff(
                customer_email="alice",
            )
        )

        self.assertEqual(
            [shipment.pk for shipment in shipments],
            [matching_shipment.pk],
        )

    # Поиск по точному номеру заказа возвращает его отгрузку.
    # Другой заказ того же клиента исключается из результата.
    def test_finds_unpaid_shipment_by_order_id(self):
        matching_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("100.00"),
        )
        OrderItem.objects.create(
            order=matching_order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=matching_order.currency_snapshot,
        )

        matching_shipment = complete_order_shipment(
            order=matching_order,
            created_by=self.manager,
        )
        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        shipments = list(
            get_unpaid_order_shipments_for_staff(
                order_id=str(matching_order.pk),
            )
        )

        self.assertEqual(
            [shipment.pk for shipment in shipments],
            [matching_shipment.pk],
        )

    # Некорректный номер заказа даёт пустой результат.
    # Ошибочное условие не превращается в показ всех долгов.
    def test_invalid_order_id_returns_empty_result(self):
        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        for order_id in ("abc", "0", "-1", "1.5", str(2**63)):
            with self.subTest(order_id=order_id):
                shipments = list(
                    get_unpaid_order_shipments_for_staff(
                        order_id=order_id,
                    )
                )

                self.assertEqual(shipments, [])