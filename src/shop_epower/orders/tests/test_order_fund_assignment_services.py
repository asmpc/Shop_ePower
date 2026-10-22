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
    reverse_customer_transaction,
)
from shop_epower.orders.models import (
    Order,
    OrderCancellationReason,
    OrderItem,
    OrderStatus,
)
from shop_epower.orders.services import (
    assign_order_funds,
    cancel_new_order,
    cancel_order_fund_assignment,
    complete_order_shipment,
    update_order_status_by_manager,
)
from shop_epower.orders.tests.helpers import create_test_order


class TestsOrderFundAssignmentServices(TestCase):
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
        self.deposit_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="assignment:service:deposit:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

    def _ship_order(self):
        product = create_test_product()
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

        return complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

    # До отгрузки назначение уменьшает доступные средства,
    # не создаёт долг и сохраняет источник денег.
    def test_assign_funds_before_shipment(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:001",
            created_by=self.manager,
        )

        self.assertEqual(assignment.order_id, self.order.pk)
        self.assertEqual(assignment.amount, Decimal("60.00"))

        account_transaction = assignment.account_transaction
        self.assertEqual(
            account_transaction.operation_type,
            AccountTransactionType.FUNDS_ASSIGNMENT,
        )
        self.assertEqual(
            account_transaction.available_delta,
            Decimal("-60.00"),
        )
        self.assertEqual(
            account_transaction.debt_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            account_transaction.created_by_id,
            self.manager.pk,
        )

        source = assignment.sources.get()
        self.assertEqual(
            source.deposit_transaction_id,
            self.deposit_transaction.pk,
        )
        self.assertEqual(source.amount, Decimal("60.00"))

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(self.order.status, OrderStatus.PROCESSING)

    # После отгрузки назначенные деньги погашают долг по этой отгрузке.
    # Доступный баланс и долг уменьшаются на сумму назначения,
    # а заказ остаётся завершённым.
    def test_assign_funds_after_shipment(self):
        shipment = self._ship_order()

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:after-shipment:001",
            created_by=self.manager,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(assignment.amount, Decimal("60.00"))

        application = assignment.applications.get()
        self.assertEqual(application.shipment_id, shipment.pk)
        self.assertEqual(application.amount, Decimal("60.00"))
        self.assertEqual(
            application.account_transaction.operation_type,
            AccountTransactionType.FUNDS_APPLICATION,
        )

        source = assignment.sources.get()
        self.assertEqual(
            source.deposit_transaction_id,
            self.deposit_transaction.pk,
        )
        self.assertEqual(source.amount, Decimal("60.00"))
        self.assertEqual(self.account.transactions.count(), 4)

    # Повтор назначения после отгрузки возвращает прежнюю запись.
    # Деньги повторно не списываются, долг повторно не погашается,
    # источники и применение назначения не дублируются.
    def test_assignment_after_shipment_is_idempotent(self):
        shipment = self._ship_order()

        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:after-shipment:repeat:001",
            created_by=self.manager,
        )
        repeated_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:after-shipment:repeat:001",
            created_by=self.manager,
        )

        self.assertEqual(
            repeated_assignment.pk,
            first_assignment.pk,
        )
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(first_assignment.sources.count(), 1)
        self.assertEqual(first_assignment.applications.count(), 1)
        self.assertEqual(shipment.fund_applications.count(), 1)

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)

    # После отгрузки нельзя назначить больше остатка по заказу,
    # даже если доступных денег и общего долга счёта достаточно.
    # Отказ не изменяет ранее созданное назначение и балансы.
    def test_assignment_after_shipment_rejects_amount_above_remaining_total(self):
        shipment = self._ship_order()

        record_customer_deposit(
            account=self.account,
            amount=Decimal("50.00"),
            operation_key="assignment:service:remaining:extra-deposit",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        record_customer_debt(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="assignment:service:remaining:other-debt",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:after-shipment:first",
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Assignment exceeds the remaining order amount.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("50.00"),
                operation_key="assignment:service:after-shipment:excess",
                created_by=self.manager,
            )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("90.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("140.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(first_assignment.sources.count(), 1)
        self.assertEqual(
            first_assignment.sources.get().amount,
            Decimal("60.00"),
        )
        self.assertEqual(shipment.fund_applications.count(), 1)
        self.assertEqual(self.account.transactions.count(), 6)

    # Ошибка сохранения применения откатывает всё новое назначение:
    # списание денег, погашение долга, назначение и его источники.
    # Ранее выполненная отгрузка остаётся без изменений.
    def test_assignment_after_shipment_rolls_back_when_application_creation_fails(self):
        shipment = self._ship_order()

        with self.assertRaisesMessage(
            RuntimeError,
            "Application creation failed.",
        ):
            with patch(
                "shop_epower.orders.services.OrderFundApplication.objects.create",
                side_effect=RuntimeError("Application creation failed."),
            ):
                assign_order_funds(
                    order=self.order,
                    amount=Decimal("60.00"),
                    operation_key="assignment:service:after-shipment:rollback",
                    created_by=self.manager,
                )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.shipments.get().pk, shipment.pk)
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertFalse(shipment.fund_applications.exists())
        self.assertFalse(
            self.deposit_transaction
            .order_fund_assignment_sources.exists()
        )
        self.assertEqual(self.account.transactions.count(), 2)

    # Завершённому заказу без записи отгрузки нельзя назначать деньги.
    # Отказ не создаёт назначение и не изменяет финансовый счёт.
    def test_assignment_rejects_completed_order_without_shipment(self):
        self.order.status = OrderStatus.COMPLETED
        self.order.save(update_fields=["status"])

        with self.assertRaisesMessage(
            ValidationError,
            "Completed order must have a matching shipment.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("60.00"),
                operation_key="assignment:service:missing-shipment",
                created_by=self.manager,
            )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertFalse(
            self.deposit_transaction
            .order_fund_assignment_sources.exists()
        )
        self.assertEqual(self.account.transactions.count(), 1)

    # Повтор запроса возвращает прежнее назначение.
    # Баланс, назначение и его источники не дублируются.
    def test_assignment_is_idempotent(self):
        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:repeat:001",
            created_by=self.manager,
        )
        repeated_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:repeat:001",
            created_by=self.manager,
        )

        self.assertEqual(
            repeated_assignment.pk,
            first_assignment.pk,
        )
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(first_assignment.sources.count(), 1)

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

    # Назначение использует поступления от старых к новым.
    # Одно назначение может включать несколько источников.
    def test_assignment_uses_multiple_deposits_in_fifo_order(self):
        self.order.total_price = Decimal("200.00")
        self.order.save(update_fields=["total_price"])

        second_deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("50.00"),
            operation_key="assignment:service:deposit:002",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("120.00"),
            operation_key="assignment:service:fifo:001",
            created_by=self.manager,
        )

        sources = (
            assignment.sources
            .order_by(
                "deposit_transaction__created_at",
                "deposit_transaction_id",
            )
            .values_list(
                "deposit_transaction_id",
                "amount",
            )
        )

        self.assertEqual(
            list(sources),
            [
                (self.deposit_transaction.pk, Decimal("100.00")),
                (second_deposit.pk, Decimal("20.00")),
            ],
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("30.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)

    # При назначении учитываются части поступлений,
    # уже использованные для других заказов этого счёта.
    def test_assignment_uses_only_remaining_deposit_funds(self):
        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:first-order:001",
            created_by=self.manager,
        )

        second_deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("50.00"),
            operation_key="assignment:service:deposit:002",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        second_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
        )

        second_assignment = assign_order_funds(
            order=second_order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:second-order:001",
            created_by=self.manager,
        )

        sources = (
            second_assignment.sources
            .order_by("deposit_transaction_id")
            .values_list(
                "deposit_transaction_id",
                "amount",
            )
        )

        self.assertEqual(
            list(sources),
            [
                (self.deposit_transaction.pk, Decimal("40.00")),
                (second_deposit.pk, Decimal("20.00")),
            ],
        )
        self.assertEqual(
            first_assignment.sources.get().amount,
            Decimal("60.00"),
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("30.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)

    # Назначение сверх стоимости заказа отклоняется.
    # Финансовое списание и связанные записи не сохраняются.
    def test_assignment_rejects_amount_above_order_total(self):
        self.order.total_price = Decimal("50.00")
        self.order.save(update_fields=["total_price"])

        with self.assertRaisesMessage(
            ValidationError,
            "Assignment exceeds the remaining order amount.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("60.00"),
                operation_key="assignment:service:above-total:001",
                created_by=self.manager,
            )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertFalse(
            self.deposit_transaction
            .order_fund_assignment_sources.exists()
        )

    # Сумма всех назначений не может превышать стоимость заказа.
    # При отказе первое назначение остаётся без изменений.
    def test_assignment_rejects_amount_above_remaining_order_total(self):
        record_customer_deposit(
            account=self.account,
            amount=Decimal("50.00"),
            operation_key="assignment:service:deposit:002",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:remaining:first",
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Assignment exceeds the remaining order amount.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("50.00"),
                operation_key="assignment:service:remaining:second",
                created_by=self.manager,
            )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("90.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(
            first_assignment.sources.get().amount,
            Decimal("60.00"),
        )

    # Нельзя назначить больше доступного остатка счёта.
    # Неудачная попытка не создаёт финансовых и связанных записей.
    def test_assignment_rejects_insufficient_available_funds(self):
        self.order.total_price = Decimal("200.00")
        self.order.save(update_fields=["total_price"])

        with self.assertRaisesMessage(
            ValidationError,
            "Resulting available balance cannot be negative.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("110.00"),
                operation_key="assignment:service:insufficient:001",
                created_by=self.manager,
            )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertFalse(
            self.deposit_transaction
            .order_fund_assignment_sources.exists()
        )

    # Ошибка сохранения источника откатывает назначение,
    # финансовую операцию и изменение баланса.
    def test_assignment_rolls_back_when_source_creation_fails(self):
        with self.assertRaisesMessage(
            RuntimeError,
            "Source creation failed.",
        ):
            with patch(
                "shop_epower.orders.services.OrderFundAssignmentSource.objects.create",
                side_effect=RuntimeError("Source creation failed."),
            ):
                assign_order_funds(
                    order=self.order,
                    amount=Decimal("60.00"),
                    operation_key="assignment:service:rollback:001",
                    created_by=self.manager,
                )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertFalse(
            self.deposit_transaction
            .order_fund_assignment_sources.exists()
        )

    # Ключ существующего назначения нельзя использовать
    # для другого заказа, даже при совпадении счёта и суммы.
    def test_assignment_rejects_operation_key_for_another_order(self):
        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:shared-key:001",
            created_by=self.manager,
        )
        second_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for another order.",
        ):
            assign_order_funds(
                order=second_order,
                amount=Decimal("60.00"),
                operation_key="assignment:service:shared-key:001",
                created_by=self.manager,
            )

        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertFalse(second_order.fund_assignments.exists())
        self.assertEqual(first_assignment.sources.count(), 1)

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

    # Клиент не может назначать средства даже на свой заказ.
    # Отказ не изменяет баланс и не создаёт назначение.
    def test_customer_cannot_assign_order_funds(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Only managers and administrators can assign order funds.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("60.00"),
                operation_key="assignment:service:customer:001",
                created_by=self.user,
            )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())

    # Администратор может назначать средства.
    # Финансовая история сохраняет его как инициатора ADMIN.
    def test_admin_can_assign_order_funds(self):
        admin = create_test_admin()

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:admin:001",
            created_by=admin,
        )

        self.assertEqual(assignment.order_id, self.order.pk)
        self.assertEqual(
            assignment.account_transaction.actor_type,
            AccountTransactionActorType.ADMIN,
        )
        self.assertEqual(
            assignment.account_transaction.created_by_id,
            admin.pk,
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Неактивному сотруднику назначение средств запрещено
    # независимо от его роли: менеджер или администратор.
    def test_inactive_staff_cannot_assign_order_funds(self):
        for staff in (self.manager, create_test_admin()):
            with self.subTest(role=staff.role):
                staff.is_active = False
                staff.save(update_fields=["is_active"])

                with self.assertRaisesMessage(
                    ValidationError,
                    "Only managers and administrators can assign order funds.",
                ):
                    assign_order_funds(
                        order=self.order,
                        amount=Decimal("60.00"),
                        operation_key=f"assignment:service:inactive:{staff.pk}",
                        created_by=staff,
                    )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())

    # Сервис проверяет актуальный статус заказа в базе.
    # Устаревший объект не позволяет назначить деньги на отменённый заказ.
    def test_assignment_rejects_cancelled_order_from_database(self):
        Order.objects.filter(pk=self.order.pk).update(
            status=OrderStatus.CANCELLED,
        )

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Funds cannot be assigned to an order in this status.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("60.00"),
                operation_key="assignment:service:cancelled:001",
                created_by=self.manager,
            )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())

    # Счёт заказа должен принадлежать покупателю.
    # Ошибочная ссылка на чужой счёт не позволяет списать деньги.
    def test_assignment_rejects_another_customers_account(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(
            user=other_user,
        )
        record_customer_deposit(
            account=other_account,
            amount=Decimal("100.00"),
            operation_key="assignment:service:other-deposit:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        self.order.customer_account = other_account
        self.order.save(update_fields=["customer_account"])

        with self.assertRaisesMessage(
            ValidationError,
            "Order must reference its owner's matching customer account.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("60.00"),
                operation_key="assignment:service:foreign-account:001",
                created_by=self.manager,
            )

        for account in (self.account, other_account):
            with self.subTest(account_id=account.pk):
                account.refresh_from_db()
                self.assertEqual(
                    account.available_balance,
                    Decimal("100.00"),
                )
                self.assertEqual(
                    account.debt_balance,
                    Decimal("0.00"),
                )
                self.assertEqual(account.transactions.count(), 1)

        self.assertFalse(self.order.fund_assignments.exists())

    # Заказ юридического лица нельзя оплачивать
    # с личного счёта того же покупателя.
    def test_assignment_rejects_account_type_mismatch(self):
        self.order.is_legal_entity = True
        self.order.save(update_fields=["is_legal_entity"])

        with self.assertRaisesMessage(
            ValidationError,
            "Order must reference its owner's matching customer account.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("60.00"),
                operation_key="assignment:service:wrong-account-type:001",
                created_by=self.manager,
            )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())

    # Отменённое поступление остаётся в истории,
    # но не используется как источник нового назначения.
    def test_assignment_excludes_reversed_deposit(self):
        second_deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="assignment:service:deposit:002",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        reverse_customer_transaction(
            original_transaction=self.deposit_transaction,
            operation_key="assignment:service:reverse-deposit:001",
            actor_type=AccountTransactionActorType.SYSTEM,
            comment="Receipt was recorded by mistake.",
        )

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:after-reversal:001",
            created_by=self.manager,
        )

        source = assignment.sources.get()
        self.assertEqual(
            source.deposit_transaction_id,
            second_deposit.pk,
        )
        self.assertEqual(source.amount, Decimal("60.00"))
        self.assertFalse(
            self.deposit_transaction
            .order_fund_assignment_sources.exists()
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)

    # Повторное использование ключа с другой суммой запрещено.
    # Исходное назначение и баланс остаются без изменений.
    def test_assignment_rejects_operation_key_with_different_amount(self):
        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:amount-conflict:001",
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for different transaction data.",
        ):
            assign_order_funds(
                order=self.order,
                amount=Decimal("30.00"),
                operation_key="assignment:service:amount-conflict:001",
                created_by=self.manager,
            )

        first_assignment.refresh_from_db()
        self.assertEqual(first_assignment.amount, Decimal("60.00"))
        self.assertEqual(
            first_assignment.sources.get().amount,
            Decimal("60.00"),
        )
        self.assertEqual(self.order.fund_assignments.count(), 1)

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

    # Отмена назначения возвращает доступные средства без создания долга.
    # Назначение и источники сохраняются, поступление не отменяется.
    def test_cancel_assignment_before_shipment(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:before-cancel:001",
            created_by=self.manager,
        )
        source = assignment.sources.get()
        comment = "Funds were assigned to the wrong order."

        reversal = cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:cancel:001",
            created_by=self.manager,
            comment=comment,
        )

        self.assertEqual(
            reversal.operation_type,
            AccountTransactionType.REVERSAL,
        )
        self.assertEqual(
            reversal.reversal_of_id,
            assignment.account_transaction_id,
        )
        self.assertEqual(reversal.available_delta, Decimal("60.00"))
        self.assertEqual(reversal.debt_delta, Decimal("0.00"))
        self.assertEqual(reversal.comment, comment)
        self.assertEqual(reversal.created_by_id, self.manager.pk)
        self.assertEqual(
            reversal.actor_type,
            AccountTransactionActorType.MANAGER,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(assignment.sources.get().pk, source.pk)
        self.assertFalse(
            self.account.transactions.filter(
                reversal_of=self.deposit_transaction,
            ).exists()
        )

    # Отмена назначения после отгрузки возвращает доступные деньги
    # и восстанавливает долг. Отгрузка, поступление денег
    # и история назначения сохраняются.
    def test_cancel_assignment_after_shipment(self):
        shipment = self._ship_order()
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:after-shipment:before-cancel",
            created_by=self.manager,
        )
        application = assignment.applications.get()
        source = assignment.sources.get()
        comment = "Funds were assigned to the wrong order."

        reversal = cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:after-shipment:cancel",
            created_by=self.manager,
            comment=comment,
        )

        self.assertEqual(
            reversal.reversal_of_id,
            assignment.account_transaction_id,
        )
        self.assertEqual(reversal.available_delta, Decimal("60.00"))
        self.assertEqual(reversal.debt_delta, Decimal("0.00"))
        self.assertEqual(reversal.comment, comment)

        application_reversal = self.account.transactions.get(
            reversal_of_id=application.account_transaction_id,
        )
        self.assertEqual(
            application_reversal.operation_type,
            AccountTransactionType.REVERSAL,
        )
        self.assertEqual(
            application_reversal.available_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            application_reversal.debt_delta,
            Decimal("60.00"),
        )
        self.assertEqual(application_reversal.comment, comment)
        self.assertEqual(
            application_reversal.created_by_id,
            self.manager.pk,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.shipments.get().pk, shipment.pk)
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(assignment.sources.get().pk, source.pk)
        self.assertEqual(assignment.applications.get().pk, application.pk)
        self.assertEqual(self.account.transactions.count(), 6)
        self.assertFalse(
            self.account.transactions.filter(
                reversal_of_id__in=[
                    self.deposit_transaction.pk,
                    shipment.debt_transaction_id,
                ],
            ).exists()
        )

    # Повтор отмены после отгрузки возвращает прежнюю обратную операцию.
    # Доступные деньги и долг восстанавливаются только один раз.
    def test_cancel_assignment_after_shipment_is_idempotent(self):
        shipment = self._ship_order()
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:cancel-repeat:assign",
            created_by=self.manager,
        )
        application = assignment.applications.get()
        comment = "Funds were assigned to the wrong order."

        first_reversal = cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:cancel-repeat:cancel",
            created_by=self.manager,
            comment=comment,
        )
        repeated_reversal = cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:cancel-repeat:cancel",
            created_by=self.manager,
            comment=comment,
        )

        self.assertEqual(repeated_reversal.pk, first_reversal.pk)
        self.assertEqual(
            self.account.transactions.filter(
                reversal_of_id=application.account_transaction_id,
            ).count(),
            1,
        )
        self.assertEqual(
            self.account.transactions.filter(
                reversal_of_id=assignment.account_transaction_id,
            ).count(),
            1,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 6)
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.shipments.get().pk, shipment.pk)

    # Если отмена назначения завершается ошибкой,
    # предшествующая отмена применения тоже откатывается.
    # Балансы и история остаются в состоянии до попытки отмены.
    def test_cancel_assignment_after_shipment_rolls_back_on_failure(self):
        shipment = self._ship_order()
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:cancel-rollback:assign",
            created_by=self.manager,
        )

        def reverse_application_then_fail(
            *,
            original_transaction,
            **kwargs,
        ):
            if original_transaction.pk == assignment.account_transaction_id:
                raise RuntimeError("Assignment reversal failed.")

            return reverse_customer_transaction(
                original_transaction=original_transaction,
                **kwargs,
            )

        with self.assertRaisesMessage(
            RuntimeError,
            "Assignment reversal failed.",
        ):
            with patch(
                "shop_epower.orders.services.reverse_customer_transaction",
                side_effect=reverse_application_then_fail,
            ):
                cancel_order_fund_assignment(
                    assignment=assignment,
                    operation_key="assignment:service:cancel-rollback:cancel",
                    created_by=self.manager,
                    comment="Funds were assigned to the wrong order.",
                )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)
        self.assertFalse(
            self.account.transactions.filter(
                operation_type=AccountTransactionType.REVERSAL,
            ).exists()
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.shipments.get().pk, shipment.pk)
        self.assertEqual(self.order.fund_assignments.get().pk, assignment.pk)
        self.assertEqual(assignment.sources.count(), 1)
        self.assertEqual(assignment.applications.count(), 1)

    # После отмены назначения деньги можно использовать заново.
    # Исторические записи сохраняются, но не уменьшают доступную
    # для нового назначения сумму заказа и поступления.
    def test_cancelled_assignment_after_shipment_can_be_assigned_again(self):
        shipment = self._ship_order()
        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:after-shipment:reuse:first",
            created_by=self.manager,
        )
        cancel_order_fund_assignment(
            assignment=first_assignment,
            operation_key="assignment:service:after-shipment:reuse:cancel",
            created_by=self.manager,
            comment="Incorrect assignment amount.",
        )

        new_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("100.00"),
            operation_key="assignment:service:after-shipment:reuse:new",
            created_by=self.manager,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertNotEqual(new_assignment.pk, first_assignment.pk)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.fund_assignments.count(), 2)
        self.assertEqual(
            self.order.fund_assignments.filter(
                account_transaction__reversal__isnull=True,
            ).count(),
            1,
        )
        self.assertEqual(shipment.fund_applications.count(), 2)
        self.assertEqual(
            shipment.fund_applications.filter(
                account_transaction__reversal__isnull=True,
            ).count(),
            1,
        )

        source = new_assignment.sources.get()
        self.assertEqual(
            source.deposit_transaction_id,
            self.deposit_transaction.pk,
        )
        self.assertEqual(source.amount, Decimal("100.00"))
        self.assertEqual(self.account.transactions.count(), 8)

    # После отмены средства можно назначить заново.
    # Историческое назначение не занимает сумму заказа и поступления.
    def test_cancelled_assignment_funds_can_be_assigned_again(self):
        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:reuse:first",
            created_by=self.manager,
        )

        cancel_order_fund_assignment(
            assignment=first_assignment,
            operation_key="assignment:service:reuse:cancel",
            created_by=self.manager,
            comment="Assignment was made by mistake.",
        )

        new_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:reuse:second",
            created_by=self.manager,
        )

        self.assertNotEqual(new_assignment.pk, first_assignment.pk)
        self.assertEqual(self.order.fund_assignments.count(), 2)
        self.assertEqual(
            self.order.fund_assignments.filter(
                account_transaction__reversal__isnull=True,
            ).count(),
            1,
        )

        new_source = new_assignment.sources.get()
        self.assertEqual(
            new_source.deposit_transaction_id,
            self.deposit_transaction.pk,
        )
        self.assertEqual(new_source.amount, Decimal("60.00"))
        self.assertEqual(
            first_assignment.sources.get().amount,
            Decimal("60.00"),
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)

    # Отмена требует непустого комментария.
    # При отказе назначение действует, деньги остаются назначенными.
    def test_cancel_assignment_requires_comment(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:comment:assign",
            created_by=self.manager,
        )

        for comment in ("", "   ", None):
            with self.subTest(comment=comment):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Cancellation comment is required.",
                ):
                    cancel_order_fund_assignment(
                        assignment=assignment,
                        operation_key="assignment:service:comment:cancel",
                        created_by=self.manager,
                        comment=comment,
                    )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(assignment.sources.count(), 1)
        self.assertFalse(
            self.account.transactions.filter(
                reversal_of_id=assignment.account_transaction_id,
            ).exists()
        )

    # Отмена выбранного назначения освобождает только его сумму.
    # Другие назначения этого заказа продолжают действовать.
    def test_cancel_assignment_preserves_other_assignments(self):
        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:selected:first",
            created_by=self.manager,
        )
        second_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("30.00"),
            operation_key="assignment:service:selected:second",
            created_by=self.manager,
        )

        reversal = cancel_order_fund_assignment(
            assignment=first_assignment,
            operation_key="assignment:service:selected:cancel",
            created_by=self.manager,
            comment="Only the first assignment was incorrect.",
        )

        self.assertEqual(
            reversal.reversal_of_id,
            first_assignment.account_transaction_id,
        )
        self.assertEqual(self.order.fund_assignments.count(), 2)

        active_assignments = self.order.fund_assignments.filter(
            account_transaction__reversal__isnull=True,
        )
        self.assertEqual(
            list(active_assignments),
            [second_assignment],
        )
        self.assertEqual(
            first_assignment.sources.get().amount,
            Decimal("60.00"),
        )
        self.assertEqual(
            second_assignment.sources.get().amount,
            Decimal("30.00"),
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("70.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)

    # Повтор отмены с тем же ключом возвращает прежнюю операцию.
    # Деньги возвращаются на доступный баланс только один раз.
    def test_cancel_assignment_is_idempotent(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:cancel-repeat:assign",
            created_by=self.manager,
        )
        comment = "Assignment was made by mistake."

        first_reversal = cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:cancel-repeat:cancel",
            created_by=self.manager,
            comment=comment,
        )
        repeated_reversal = cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:cancel-repeat:cancel",
            created_by=self.manager,
            comment=comment,
        )

        self.assertEqual(repeated_reversal.pk, first_reversal.pk)

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.account.transactions.filter(
                reversal_of_id=assignment.account_transaction_id,
            ).count(),
            1,
        )
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(assignment.sources.count(), 1)

    # Новый ключ не позволяет повторно отменить назначение.
    # Уже возвращённые средства не зачисляются второй раз.
    def test_cancel_assignment_rejects_second_cancellation(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:double-cancel:assign",
            created_by=self.manager,
        )

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:double-cancel:first",
            created_by=self.manager,
            comment="Assignment was made by mistake.",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Transaction has already been reversed.",
        ):
            cancel_order_fund_assignment(
                assignment=assignment,
                operation_key="assignment:service:double-cancel:second",
                created_by=self.manager,
                comment="Another cancellation attempt.",
            )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.account.transactions.filter(
                reversal_of_id=assignment.account_transaction_id,
            ).count(),
            1,
        )

    # Клиент не может отменить назначение даже на свой заказ.
    # Средства остаются назначенными, отмена не записывается.
    def test_customer_cannot_cancel_assignment(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:customer-cancel:assign",
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Only managers and administrators can cancel order fund assignments.",
        ):
            cancel_order_fund_assignment(
                assignment=assignment,
                operation_key="assignment:service:customer-cancel:cancel",
                created_by=self.user,
                comment="Customer attempts to cancel the assignment.",
            )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertFalse(
            self.account.transactions.filter(
                reversal_of_id=assignment.account_transaction_id,
            ).exists()
        )

    # Администратор может отменить назначение менеджера.
    # Каждая финансовая операция сохраняет своего инициатора.
    def test_admin_can_cancel_assignment(self):
        admin = create_test_admin()
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:admin-cancel:assign",
            created_by=self.manager,
        )

        reversal = cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:admin-cancel:cancel",
            created_by=admin,
            comment="Administrator corrected the assignment.",
        )

        self.assertEqual(
            reversal.actor_type,
            AccountTransactionActorType.ADMIN,
        )
        self.assertEqual(reversal.created_by_id, admin.pk)

        assignment.account_transaction.refresh_from_db()
        self.assertEqual(
            assignment.account_transaction.created_by_id,
            self.manager.pk,
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)

    # Неактивному сотруднику отмена назначения запрещена.
    # Его роль не позволяет обойти блокировку учётной записи.
    def test_inactive_staff_cannot_cancel_assignment(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:inactive-cancel:assign",
            created_by=self.manager,
        )

        for staff in (self.manager, create_test_admin()):
            with self.subTest(role=staff.role):
                staff.is_active = False
                staff.save(update_fields=["is_active"])

                with self.assertRaisesMessage(
                    ValidationError,
                    "Only managers and administrators can cancel order fund assignments.",
                ):
                    cancel_order_fund_assignment(
                        assignment=assignment,
                        operation_key=f"assignment:service:inactive-cancel:{staff.pk}",
                        created_by=staff,
                        comment="Inactive employee attempts cancellation.",
                    )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertFalse(
            self.account.transactions.filter(
                reversal_of_id=assignment.account_transaction_id,
            ).exists()
        )

    # Отменённый заказ не блокирует освобождение назначенных средств.
    # Отмена назначения не меняет статус самого заказа.
    def test_cancel_assignment_for_cancelled_order(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:cancelled-order:assign",
            created_by=self.manager,
        )

        self.order.status = OrderStatus.CANCELLED
        self.order.save(update_fields=["status"])

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:service:cancelled-order:cancel",
            created_by=self.manager,
            comment="Funds released from the cancelled order.",
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertFalse(
            self.order.fund_assignments.filter(
                account_transaction__reversal__isnull=True,
            ).exists()
        )

    # Отмена заказа менеджером освобождает все действующие назначения.
    # Деньги остаются на счёте клиента, финансовая история сохраняется.
    def test_manager_order_cancellation_releases_all_assignments(self):
        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:order-cancel:first",
            created_by=self.manager,
        )
        second_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("30.00"),
            operation_key="assignment:service:order-cancel:second",
            created_by=self.manager,
        )

        update_order_status_by_manager(
            order=self.order,
            user=self.manager,
            new_status=OrderStatus.CANCELLED,
            cancellation_reason=OrderCancellationReason.CLIENT_REFUSED,
            cancellation_comment="Customer cancelled the order.",
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        self.assertEqual(self.account.transactions.count(), 5)
        self.assertEqual(self.order.fund_assignments.count(), 2)
        self.assertFalse(
            self.order.fund_assignments.filter(
                account_transaction__reversal__isnull=True,
            ).exists()
        )

        reversed_transactions = self.account.transactions.filter(
            operation_type=AccountTransactionType.REVERSAL,
        ).values_list("reversal_of_id", flat=True)

        self.assertCountEqual(
            reversed_transactions,
            [
                first_assignment.account_transaction_id,
                second_assignment.account_transaction_id,
            ],
        )
        self.assertEqual(
            self.deposit_transaction
            .order_fund_assignment_sources.count(),
            2,
        )

    # Ошибка освобождения средств откатывает отмену заказа.
    # Исходное назначение продолжает действовать.
    def test_manager_order_cancellation_rolls_back_when_release_fails(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:order-rollback:assign",
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Assignment release failed.",
        ):
            with patch(
                "shop_epower.orders.services.cancel_order_fund_assignment",
                side_effect=RuntimeError("Assignment release failed."),
            ):
                update_order_status_by_manager(
                    order=self.order,
                    user=self.manager,
                    new_status=OrderStatus.CANCELLED,
                    cancellation_reason=OrderCancellationReason.CLIENT_REFUSED,
                    cancellation_comment="Customer cancelled the order.",
                )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.cancellation_reason, "")
        self.assertEqual(self.order.cancellation_comment, "")
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertTrue(
            self.order.fund_assignments.filter(
                pk=assignment.pk,
                account_transaction__reversal__isnull=True,
            ).exists()
        )

    # Отмена клиентом своего нового заказа освобождает назначенные деньги.
    # Финансовая история сохраняет клиента как инициатора отмены.
    def test_customer_order_cancellation_releases_assignment(self):
        self.order.status = OrderStatus.NEW
        self.order.save(update_fields=["status"])

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:customer-order:assign",
            created_by=self.manager,
        )

        cancel_new_order(
            order=self.order,
            user=self.user,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        self.assertEqual(self.account.transactions.count(), 3)

        reversal = self.account.transactions.get(
            reversal_of_id=assignment.account_transaction_id,
        )
        self.assertEqual(
            reversal.actor_type,
            AccountTransactionActorType.CUSTOMER,
        )
        self.assertEqual(reversal.created_by_id, self.user.pk)
        self.assertTrue(reversal.comment.strip())

        self.assertEqual(self.order.fund_assignments.count(), 1)
        self.assertEqual(assignment.sources.count(), 1)

    # Ошибка освобождения средств откатывает клиентскую отмену заказа.
    # Заказ остаётся новым, назначенные средства не освобождаются.
    def test_customer_order_cancellation_rolls_back_when_release_fails(self):
        self.order.status = OrderStatus.NEW
        self.order.save(update_fields=["status"])

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:service:customer-rollback:assign",
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Assignment release failed.",
        ):
            with patch(
                "shop_epower.orders.services._cancel_order_fund_assignment",
                side_effect=RuntimeError("Assignment release failed."),
            ):
                cancel_new_order(
                    order=self.order,
                    user=self.user,
                )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertTrue(
            self.order.fund_assignments.filter(
                pk=assignment.pk,
                account_transaction__reversal__isnull=True,
            ).exists()
        )