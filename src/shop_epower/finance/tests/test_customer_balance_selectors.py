from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.models import CustomerAccount
from shop_epower.finance.selectors import get_customer_account_balances
from shop_epower.finance.services import (
    create_legal_customer_account,
    create_personal_customer_account,
)
from shop_epower.orders.models import (
    OrderItem,
    OrderStatus,
)
from shop_epower.orders.services import (
    assign_order_funds,
    cancel_order_fund_assignment,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import PaymentMethod
from shop_epower.payments.services import record_manual_order_payment


class TestsCustomerBalanceSelectors(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.NEW,
            total_price=Decimal("100.00"),
        )

    def _create_prepayment_assignment(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="balance:selector:receipt:001",
            created_by=self.manager,
        )
        return assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="balance:selector:assign:001",
            created_by=self.manager,
        )

    def _ship_order(self):
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

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

    # Существующий счёт без операций возвращается с нулевыми показателями.
    # Чтение балансов не создаёт счета или финансовые операции.
    def test_account_without_operations_has_zero_balances(self):
        accounts = list(
            get_customer_account_balances(
                user=self.user,
            )
        )

        self.assertEqual(len(accounts), 1)

        account = accounts[0]

        self.assertEqual(account.pk, self.account.pk)
        self.assertEqual(account.currency, self.account.currency)
        self.assertEqual(
            account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("0.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("0.00"),
        )

        self.assertEqual(CustomerAccount.objects.count(), 1)
        self.assertFalse(self.account.transactions.exists())

    # До отгрузки назначенные деньги показываются как предоплата.
    # Чтение показателей не создаёт новых финансовых операций.
    def test_account_shows_assigned_prepayment_before_shipment(self):
        self._create_prepayment_assignment()

        account = get_customer_account_balances(
            user=self.user,
        ).get(pk=self.account.pk)

        self.assertEqual(
            account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("60.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(self.order.fund_assignments.count(), 1)

    # Применённые к отгрузке деньги больше не являются предоплатой.
    # Селектор показывает доступные 40, предоплату 0 и долг 40,
    # сохраняя финансовую историю без изменений.
    def test_applied_funds_are_not_shown_as_assigned_prepayment(self):
        assignment = self._create_prepayment_assignment()
        self._ship_order()

        account = get_customer_account_balances(
            user=self.user,
        ).get(pk=self.account.pk)

        self.assertEqual(
            account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("0.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("40.00"),
        )
        self.assertEqual(self.account.transactions.count(), 4)
        self.assertEqual(self.order.shipments.count(), 1)
        self.assertEqual(assignment.applications.count(), 1)

    # Отменённое назначение сохраняется в истории,
    # но больше не входит в назначенную предоплату.
    # Освобождённые деньги снова доступны клиенту.
    def test_cancelled_assignment_is_not_shown_as_assigned_prepayment(self):
        assignment = self._create_prepayment_assignment()

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="balance:selector:cancel:001",
            created_by=self.manager,
            comment="Assignment entered by mistake.",
        )

        account = get_customer_account_balances(
            user=self.user,
        ).get(pk=self.account.pk)

        self.assertEqual(
            account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("0.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            assignment.pk,
        )
        self.assertEqual(assignment.sources.count(), 1)

    # После отмены назначения отгруженного заказа
    # восстанавливаются доступные деньги и долг.
    # Отменённые назначение и применение не образуют предоплату.
    def test_cancelled_applied_funds_do_not_affect_assigned_prepayment(self):
        assignment = self._create_prepayment_assignment()
        shipment = self._ship_order()
        application = assignment.applications.get()

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="balance:selector:cancel-after-shipment",
            created_by=self.manager,
            comment="Cancel incorrect shipment settlement.",
        )

        account = get_customer_account_balances(
            user=self.user,
        ).get(pk=self.account.pk)

        self.assertEqual(
            account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("0.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 6)
        self.assertEqual(self.order.shipments.get().pk, shipment.pk)
        self.assertEqual(
            assignment.applications.get().pk,
            application.pk,
        )

    # Селектор возвращает только счета указанного пользователя.
    # Чужие назначения не попадают в сумму его предоплаты.
    def test_balances_include_only_requested_user_accounts(self):
        self._create_prepayment_assignment()

        other_user = create_test_user()
        other_account = create_personal_customer_account(
            user=other_user,
        )
        other_order = create_test_order(
            user=other_user,
            customer_account=other_account,
            status=OrderStatus.NEW,
            total_price=Decimal("200.00"),
        )
        record_manual_order_payment(
            order=other_order,
            amount=Decimal("200.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="balance:selector:other-receipt",
            created_by=self.manager,
        )
        assign_order_funds(
            order=other_order,
            amount=Decimal("150.00"),
            operation_key="balance:selector:other-assignment",
            created_by=self.manager,
        )

        accounts = list(
            get_customer_account_balances(
                user=self.user,
            )
        )

        self.assertEqual(len(accounts), 1)

        account = accounts[0]

        self.assertEqual(account.pk, self.account.pk)
        self.assertEqual(
            account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("60.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(CustomerAccount.objects.count(), 2)

    # Личный и юридический счета пользователя учитываются раздельно.
    # Применение денег личного счёта не уменьшает предоплату юридического.
    def test_personal_and_legal_account_balances_are_separate(self):
        self._create_prepayment_assignment()
        self._ship_order()

        profile = create_test_legal_profile(
            user=self.user,
        )
        legal_account = create_legal_customer_account(
            legal_profile=profile,
        )
        legal_order = create_test_order(
            user=self.user,
            customer_account=legal_account,
            is_legal_entity=True,
            total_price=Decimal("200.00"),
        )

        record_manual_order_payment(
            order=legal_order,
            amount=Decimal("200.00"),
            method=PaymentMethod.INVOICE,
            operation_key="balance:selector:legal-receipt",
            created_by=self.manager,
        )
        assign_order_funds(
            order=legal_order,
            amount=Decimal("150.00"),
            operation_key="balance:selector:legal-assignment",
            created_by=self.manager,
        )

        accounts = list(
            get_customer_account_balances(
                user=self.user,
            )
        )

        self.assertEqual(len(accounts), 2)

        balances = {
            account.pk: account
            for account in accounts
        }
        personal_balance = balances[self.account.pk]
        legal_balance = balances[legal_account.pk]

        self.assertEqual(
            personal_balance.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            personal_balance.assigned_prepayment,
            Decimal("0.00"),
        )
        self.assertEqual(
            personal_balance.debt_balance,
            Decimal("40.00"),
        )

        self.assertEqual(
            legal_balance.available_balance,
            Decimal("50.00"),
        )
        self.assertEqual(
            legal_balance.assigned_prepayment,
            Decimal("150.00"),
        )
        self.assertEqual(
            legal_balance.debt_balance,
            Decimal("0.00"),
        )

    # Пользователь без финансовых счетов получает пустой результат.
    # Чтение балансов не создаёт счёт автоматически.
    def test_user_without_accounts_gets_empty_balances(self):
        user_without_account = create_test_user()
        account_count_before = CustomerAccount.objects.count()

        accounts = list(
            get_customer_account_balances(
                user=user_without_account,
            )
        )

        self.assertEqual(accounts, [])
        self.assertEqual(
            CustomerAccount.objects.count(),
            account_count_before,
        )

    # Балансы учитывают несколько назначений разных заказов.
    # Использованные при отгрузке деньги исключаются из предоплаты.
    def test_balances_sum_assignments_across_multiple_orders(self):
        self._create_prepayment_assignment()

        assign_order_funds(
            order=self.order,
            amount=Decimal("20.00"),
            operation_key="balance:selector:first-order-extra",
            created_by=self.manager,
        )
        self._ship_order()

        second_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("200.00"),
        )
        record_manual_order_payment(
            order=second_order,
            amount=Decimal("200.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="balance:selector:second-order-receipt",
            created_by=self.manager,
        )
        assign_order_funds(
            order=second_order,
            amount=Decimal("150.00"),
            operation_key="balance:selector:second-order-assignment",
            created_by=self.manager,
        )

        account = get_customer_account_balances(
            user=self.user,
        ).get(pk=self.account.pk)

        self.assertEqual(
            account.available_balance,
            Decimal("70.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("150.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("20.00"),
        )

    # Балансы обоих счетов загружаются одним запросом.
    # Чтение показателей не вызывает дополнительных запросов.
    def test_account_balances_are_loaded_in_one_query(self):
        self._create_prepayment_assignment()

        profile = create_test_legal_profile(
            user=self.user,
        )
        legal_account = create_legal_customer_account(
            legal_profile=profile,
        )

        with self.assertNumQueries(1):
            accounts = list(
                get_customer_account_balances(
                    user=self.user,
                )
            )
            balances = {
                account.pk: (
                    account.available_balance,
                    account.assigned_prepayment,
                    account.debt_balance,
                    account.currency,
                )
                for account in accounts
            }

        self.assertEqual(
            balances,
            {
                self.account.pk: (
                    Decimal("40.00"),
                    Decimal("60.00"),
                    Decimal("0.00"),
                    self.account.currency,
                ),
                legal_account.pk: (
                    Decimal("0.00"),
                    Decimal("0.00"),
                    Decimal("0.00"),
                    legal_account.currency,
                ),
            },
        )