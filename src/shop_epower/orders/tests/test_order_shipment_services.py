from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.models import (
    AccountTransactionActorType,
    AccountTransactionType,
)
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_debt,
    record_customer_deposit,
)
from shop_epower.orders.models import (
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
)
from shop_epower.orders.services import (
    assign_order_funds,
    cancel_order_fund_assignment,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order


class TestsOrderShipmentServices(TestCase):
    def setUp(self):
        self.user = create_test_user()
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
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("50.00"),
            quantity=2,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

    # Полная отгрузка без предоплаты создаёт обязательство
    # на всю стоимость заказа и переводит заказ в COMPLETED.
    # Доступные средства не меняются, фиктивное применение не создаётся.
    def test_full_shipment_without_prepayment_creates_full_debt(self):
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        shipment.refresh_from_db()
        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(shipment.order_id, self.order.pk)
        self.assertEqual(
            shipment.customer_account_id,
            self.account.pk,
        )
        self.assertEqual(
            shipment.total_amount,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.order.status,
            OrderStatus.COMPLETED,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            shipment.debt_transaction.operation_type,
            AccountTransactionType.DEBT_INCREASE,
        )
        self.assertEqual(
            shipment.debt_transaction.available_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            shipment.debt_transaction.debt_delta,
            Decimal("100.00"),
        )
        self.assertEqual(self.order.shipments.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(shipment.fund_applications.exists())

    # Полная отгрузка копирует позицию заказа целиком:
    # сохраняет исходную связь и снимки названия, цены,
    # количества, суммы и валюты.
    def test_full_shipment_copies_order_item_snapshots(self):
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.assertEqual(shipment.items.count(), 1)

        shipment_item = shipment.items.get(
            order_item=self.order_item,
        )

        self.assertEqual(
            shipment_item.order_item_id,
            self.order_item.pk,
        )
        self.assertEqual(
            shipment_item.product_name,
            self.product.name,
        )
        self.assertEqual(
            shipment_item.unit_price,
            Decimal("50.00"),
        )
        self.assertEqual(shipment_item.quantity, 2)
        self.assertEqual(
            shipment_item.total_price,
            Decimal("100.00"),
        )
        self.assertEqual(
            shipment_item.currency_snapshot,
            self.order.currency_snapshot,
        )

    # Отгрузка начисляет полное обязательство и применяет предоплату.
    # Назначенные 60 уменьшают долг со 100 до 40,
    # не списывая доступные средства повторно.
    def test_full_shipment_applies_assigned_prepayment(self):
        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment:service:deposit",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="shipment:service:assignment",
            created_by=self.manager,
        )

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            shipment.debt_transaction.debt_delta,
            Decimal("100.00"),
        )

        application = shipment.fund_applications.get(
            assignment=assignment,
        )

        self.assertEqual(application.amount, Decimal("60.00"))
        self.assertEqual(
            application.account_transaction.operation_type,
            AccountTransactionType.FUNDS_APPLICATION,
        )
        self.assertEqual(
            application.account_transaction.available_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            application.account_transaction.debt_delta,
            Decimal("-60.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)

    # Полностью назначенная предоплата покрывает обязательство отгрузки.
    # Доступный баланс и долг остаются нулевыми:
    # повторного списания доступных средств нет.
    def test_fully_prepaid_shipment_leaves_zero_balances(self):
        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment:fully-prepaid:deposit",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("100.00"),
            operation_key="shipment:fully-prepaid:assignment",
            created_by=self.manager,
        )

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            shipment.debt_transaction.debt_delta,
            Decimal("100.00"),
        )

        application = shipment.fund_applications.get(
            assignment=assignment,
        )

        self.assertEqual(application.amount, Decimal("100.00"))
        self.assertEqual(
            application.account_transaction.available_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            application.account_transaction.debt_delta,
            Decimal("-100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)

    # Повторное подтверждение возвращает существующую отгрузку.
    # Обязательство, позиции и применение предоплаты
    # не создаются повторно, балансы не меняются второй раз.
    def test_repeated_shipment_returns_existing_result(self):
        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment:repeat:deposit",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="shipment:repeat:assignment",
            created_by=self.manager,
        )

        first_shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.order.refresh_from_db()

        repeated_shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            repeated_shipment.pk,
            first_shipment.pk,
        )
        self.assertEqual(
            self.order.status,
            OrderStatus.COMPLETED,
        )
        self.assertEqual(self.order.shipments.count(), 1)
        self.assertEqual(first_shipment.items.count(), 1)
        self.assertEqual(
            first_shipment.fund_applications.count(),
            1,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)

    # Ошибка сохранения применения откатывает весь процесс отгрузки:
    # обязательство, применение средств и позиции не сохраняются.
    # Ранее полученные и назначенные деньги остаются без изменений.
    def test_shipment_rolls_back_when_application_creation_fails(self):
        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment:rollback:deposit",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="shipment:rollback:assignment",
            created_by=self.manager,
        )

        with patch(
            "shop_epower.orders.services.OrderFundApplication.objects.create",
            side_effect=RuntimeError("Application save failed."),
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Application save failed.",
            ):
                complete_order_shipment(
                    order=self.order,
                    created_by=self.manager,
                )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.order_item.shipment_items.exists())
        self.assertFalse(assignment.applications.exists())
        self.assertEqual(self.account.transactions.count(), 2)

    # Клиент не может подтвердить отгрузку собственного заказа.
    # Отказ не меняет статус, балансы и финансовую историю.
    def test_customer_cannot_complete_order_shipment(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Only managers and administrators can complete order shipment.",
        ):
            complete_order_shipment(
                order=self.order,
                created_by=self.user,
            )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.account.transactions.exists())

    # Администратор может подтвердить полную отгрузку.
    # Отгрузка и финансовая операция сохраняют его авторство,
    # а тип инициатора операции записывается как ADMIN.
    def test_admin_can_complete_order_shipment(self):
        admin = create_test_admin()

        shipment = complete_order_shipment(
            order=self.order,
            created_by=admin,
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.COMPLETED,
        )
        self.assertEqual(shipment.created_by_id, admin.pk)
        self.assertEqual(
            shipment.debt_transaction.created_by_id,
            admin.pk,
        )
        self.assertEqual(
            shipment.debt_transaction.actor_type,
            AccountTransactionActorType.ADMIN,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.order.shipments.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)

    # Неактивные менеджер и администратор не могут отгружать заказ.
    # Отказ не создаёт отгрузку или финансовые операции.
    def test_inactive_staff_cannot_complete_order_shipment(self):
        for staff in (self.manager, create_test_admin()):
            with self.subTest(role=staff.role):
                staff.is_active = False
                staff.save(
                    update_fields=["is_active"],
                )

                with self.assertRaisesMessage(
                    ValidationError,
                    "Only managers and administrators can complete order shipment.",
                ):
                    complete_order_shipment(
                        order=self.order,
                        created_by=staff,
                    )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.account.transactions.exists())

    # Возврат существующей отгрузки не обходит проверку прав.
    # Клиенту запрещён вызов даже после завершения заказа менеджером.
    def test_customer_cannot_repeat_completed_shipment(self):
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.order.refresh_from_db()

        with self.assertRaisesMessage(
            ValidationError,
            "Only managers and administrators can complete order shipment.",
        ):
            complete_order_shipment(
                order=self.order,
                created_by=self.user,
            )

        self.account.refresh_from_db()

        self.assertEqual(
            self.order.shipments.get().pk,
            shipment.pk,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)

    # Отменённое назначение сохраняется в истории,
    # но при отгрузке не применяется к долгу.
    # Освобождённые деньги остаются доступными клиенту.
    def test_shipment_ignores_cancelled_fund_assignments(self):
        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment:cancelled-assignment:deposit",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="shipment:cancelled-assignment:assign",
            created_by=self.manager,
        )
        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="shipment:cancelled-assignment:cancel",
            created_by=self.manager,
            comment="Prepayment assignment was cancelled.",
        )

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            shipment.debt_transaction.debt_delta,
            Decimal("100.00"),
        )
        self.assertFalse(shipment.fund_applications.exists())
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(assignment.sources.count(), 1)
        self.assertEqual(self.account.transactions.count(), 4)

    # Назначения не могут превышать стоимость конкретной отгрузки,
    # даже если общий долг счёта позволяет списать большую сумму.
    # Отказ откатывает все изменения отгрузки.
    def test_shipment_rejects_assignments_above_its_total(self):
        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="shipment:limit:deposit",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="shipment:limit:assignment",
            created_by=self.manager,
        )

        self.order.total_price = Decimal("50.00")
        self.order.save(
            update_fields=["total_price"],
        )
        self.order_item.unit_price = Decimal("25.00")
        self.order_item.total_price = Decimal("50.00")
        self.order_item.save(
            update_fields=["unit_price", "total_price"],
        )

        record_customer_debt(
            account=self.account,
            amount=Decimal("200.00"),
            operation_key="shipment:limit:existing-debt",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Assigned funds exceed the shipment amount.",
        ):
            complete_order_shipment(
                order=self.order,
                created_by=self.manager,
            )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("200.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.order_item.shipment_items.exists())
        self.assertFalse(assignment.applications.exists())
        self.assertEqual(self.account.transactions.count(), 3)

    # Заказ без товарных позиций нельзя отгрузить.
    # Отказ не создаёт обязательство и не меняет статус заказа.
    def test_shipment_rejects_order_without_items(self):
        self.order_item.delete()

        with self.assertRaisesMessage(
            ValidationError,
            "Cannot ship an order without items.",
        ):
            complete_order_shipment(
                order=self.order,
                created_by=self.manager,
            )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.account.transactions.exists())

    # Сервис проверяет актуальный статус заказа из базы,
    # а не устаревший статус переданного объекта.
    # Уже отменённый заказ нельзя отгрузить.
    def test_shipment_rejects_cancelled_order_from_database(self):
        Order.objects.filter(
            pk=self.order.pk,
        ).update(
            status=OrderStatus.CANCELLED,
        )

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Only processing orders can be shipped.",
        ):
            complete_order_shipment(
                order=self.order,
                created_by=self.manager,
            )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.CANCELLED,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.account.transactions.exists())

    # Отгрузка не может начислить обязательство на счёт другого клиента.
    # Ошибка связи не меняет заказ и балансы обоих счетов.
    def test_shipment_rejects_another_customers_account(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(
            user=other_user,
        )

        Order.objects.filter(
            pk=self.order.pk,
        ).update(
            customer_account_id=other_account.pk,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Order must reference its owner's matching customer account.",
        ):
            complete_order_shipment(
                order=self.order,
                created_by=self.manager,
            )

        self.order.refresh_from_db()
        self.account.refresh_from_db()
        other_account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            other_account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            other_account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(other_account.transactions.exists())

    # Валюта заказа и его позиций должна совпадать с валютой счёта.
    # Несовпадение отклоняется без отгрузки и финансовых изменений.
    def test_shipment_rejects_account_currency_mismatch(self):
        other_currency = (
            "USD"
            if self.account.currency != "USD"
            else "EUR"
        )

        self.order.currency_snapshot = other_currency
        self.order.save(
            update_fields=["currency_snapshot"],
        )
        self.order_item.currency_snapshot = other_currency
        self.order_item.save(
            update_fields=["currency_snapshot"],
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Order currency must match account currency.",
        ):
            complete_order_shipment(
                order=self.order,
                created_by=self.manager,
            )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.account.transactions.exists())

    # Несогласованный итог заказа нельзя использовать для отгрузки:
    # позиции стоят 100, но в заказе сохранено 90.
    # Отказ не создаёт обязательство и не завершает заказ.
    def test_shipment_rejects_inconsistent_order_total(self):
        self.order.total_price = Decimal("90.00")
        self.order.save(
            update_fields=["total_price"],
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Order total does not match items and delivery.",
        ):
            complete_order_shipment(
                order=self.order,
                created_by=self.manager,
            )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.order_item.shipment_items.exists())
        self.assertFalse(self.account.transactions.exists())

    # Доставка, оплачиваемая магазину, входит в обязательство:
    # товары 100 плюс доставка 20 дают сумму отгрузки и долг 120.
    def test_shipment_includes_delivery_paid_to_shop(self):
        self.order.delivery_method = DeliveryMethod.SHIPPING
        self.order.delivery_cost = Decimal("20.00")
        self.order.delivery_paid_by_customer_on_receipt = False
        self.order.total_price = Decimal("120.00")
        self.order.save(
            update_fields=[
                "delivery_method",
                "delivery_cost",
                "delivery_paid_by_customer_on_receipt",
                "total_price",
            ],
        )

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            shipment.total_amount,
            Decimal("120.00"),
        )
        self.assertEqual(
            shipment.debt_transaction.debt_delta,
            Decimal("120.00"),
        )
        self.assertEqual(
            shipment.items.get().total_price,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("120.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)

    # Отдельная оплата доставки перевозчику не входит в долг магазину.
    # Стоимость доставки 20 сохраняется в заказе,
    # но обязательство отгрузки составляет только 100 за товары.
    def test_shipment_excludes_delivery_paid_to_carrier(self):
        self.order.delivery_method = DeliveryMethod.SHIPPING
        self.order.delivery_cost = Decimal("20.00")
        self.order.delivery_paid_by_customer_on_receipt = True
        self.order.total_price = Decimal("100.00")
        self.order.save(
            update_fields=[
                "delivery_method",
                "delivery_cost",
                "delivery_paid_by_customer_on_receipt",
                "total_price",
            ],
        )

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.delivery_cost,
            Decimal("20.00"),
        )
        self.assertEqual(
            shipment.total_amount,
            Decimal("100.00"),
        )
        self.assertEqual(
            shipment.debt_transaction.debt_delta,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
