from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import AccountTransactionActorType
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_debt,
)
from shop_epower.orders.services import (
    assign_order_funds,
    cancel_order_fund_assignment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    CustomerPayout,
    CustomerPayoutSource,
    PaymentMethod,
    PaymentStatus,
    PayoutMethod,
)
from shop_epower.payments.services import (
    cancel_manual_order_payment,
    record_manual_account_payment,
    record_manual_account_payout,
)


class TestsAccountPayoutServices(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )

        self.older_receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:payout:older-receipt",
            created_by=self.manager,
            comment="Money received in the office.",
        )

        self.newer_receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("60.00"),
            method=PaymentMethod.INVOICE,
            operation_key="account:payout:newer-receipt",
            created_by=self.manager,
            comment="Bank transfer received.",
        )

    # Проверяем возврат из последнего поступления по LIFO:
    # безналичное поступление может быть источником выдачи наличных.
    # Баланс уменьшается, исходное поступление сохраняет статус и способ.
    def test_cash_payout_uses_latest_bank_receipt(self):
        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:001",
            created_by=self.manager,
            comment="Customer requested a partial payout.",
        )

        self.account.refresh_from_db()
        self.newer_receipt.refresh_from_db()

        self.assertEqual(CustomerPayout.objects.count(), 1)
        self.assertEqual(payout.amount, Decimal("40.00"))
        self.assertEqual(payout.method, PayoutMethod.CASH)

        self.assertEqual(
            self.account.available_balance,
            Decimal("120.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        source = payout.sources.get()

        self.assertEqual(
            source.deposit_transaction_id,
            self.newer_receipt.deposit_transaction_id,
        )
        self.assertEqual(source.amount, Decimal("40.00"))

        self.assertEqual(self.newer_receipt.status, PaymentStatus.PAID)
        self.assertEqual(self.newer_receipt.method, PaymentMethod.INVOICE)

    # Проверяем выплату из нескольких поступлений по LIFO:
    # последнее используется полностью, недостающая сумма
    # берётся из предыдущего поступления.
    def test_payout_uses_older_receipt_when_latest_is_insufficient(self):
        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("90.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:multiple-sources",
            created_by=self.manager,
            comment="Customer requested a payout of 90 BYN.",
        )

        self.account.refresh_from_db()

        self.assertEqual(payout.amount, Decimal("90.00"))
        self.assertEqual(
            self.account.available_balance,
            Decimal("70.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        self.assertCountEqual(
            list(
                payout.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    self.newer_receipt.deposit_transaction_id,
                    Decimal("60.00"),
                ),
                (
                    self.older_receipt.deposit_transaction_id,
                    Decimal("30.00"),
                ),
            ],
        )

    # Проверяем учёт предыдущих выплат:
    # повторно использовать уже выплаченную часть поступления нельзя.
    def test_next_payout_uses_only_remaining_deposit_parts(self):
        first_payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:first",
            created_by=self.manager,
            comment="First partial payout.",
        )

        second_payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("30.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:second",
            created_by=self.manager,
            comment="Second partial payout.",
        )

        self.account.refresh_from_db()

        self.assertEqual(CustomerPayout.objects.count(), 2)
        self.assertEqual(
            self.account.available_balance,
            Decimal("90.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        self.assertCountEqual(
            list(
                second_payout.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    self.newer_receipt.deposit_transaction_id,
                    Decimal("20.00"),
                ),
                (
                    self.older_receipt.deposit_transaction_id,
                    Decimal("10.00"),
                ),
            ],
        )

        self.assertEqual(
            first_payout.sources.get().amount,
            Decimal("40.00"),
        )

    # Проверяем исключение назначенных заказу средств:
    # выплата использует только свободные части поступлений,
    # включая деньги, освобождённые снятием другого назначения.
    def test_payout_excludes_funds_assigned_to_order(self):
        first_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
        )
        second_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("40.00"),
        )

        first_assignment = assign_order_funds(
            order=first_order,
            amount=Decimal("100.00"),
            operation_key="account:payout:first-order-assignment",
            created_by=self.manager,
        )
        second_assignment = assign_order_funds(
            order=second_order,
            amount=Decimal("40.00"),
            operation_key="account:payout:second-order-assignment",
            created_by=self.manager,
        )

        cancel_order_fund_assignment(
            assignment=first_assignment,
            operation_key="account:payout:release-first-assignment",
            created_by=self.manager,
            comment="Release funds reserved for the first order.",
        )

        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("30.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:exclude-assigned-funds",
            created_by=self.manager,
            comment="Return part of the available funds.",
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
        self.assertCountEqual(
            list(
                payout.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    self.newer_receipt.deposit_transaction_id,
                    Decimal("20.00"),
                ),
                (
                    self.older_receipt.deposit_transaction_id,
                    Decimal("10.00"),
                ),
            ],
        )
        self.assertEqual(
            second_assignment.sources.get().amount,
            Decimal("40.00"),
        )

    # Проверяем исключение отменённого поступления:
    # выплата берёт деньги из предыдущего действующего поступления.
    def test_payout_skips_reversed_deposit(self):
        cancel_manual_order_payment(
            payment=self.newer_receipt,
            operation_key="account:payout:cancel-newer-receipt",
            created_by=self.manager,
            comment="Bank receipt was registered by mistake.",
        )

        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:skip-reversed-deposit",
            created_by=self.manager,
            comment="Customer requested a partial payout.",
        )

        self.account.refresh_from_db()
        self.newer_receipt.refresh_from_db()

        source = payout.sources.get()

        self.assertEqual(
            source.deposit_transaction_id,
            self.older_receipt.deposit_transaction_id,
        )
        self.assertEqual(source.amount, Decimal("40.00"))
        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.newer_receipt.status,
            PaymentStatus.CANCELLED,
        )

    # Проверяем повтор подтверждения выплаты:
    # возвращается прежняя выплата без повторного списания
    # и без дублирования записей об источниках.
    def test_repeated_payout_returns_existing_payout(self):
        payout_data = {
            "account": self.account,
            "amount": Decimal("40.00"),
            "method": PayoutMethod.CASH,
            "operation_key": "account:payout:repeated-request",
            "created_by": self.manager,
            "comment": "Customer requested a partial payout.",
        }

        first_payout = record_manual_account_payout(**payout_data)
        repeated_payout = record_manual_account_payout(**payout_data)

        self.account.refresh_from_db()

        self.assertEqual(repeated_payout.pk, first_payout.pk)
        self.assertEqual(CustomerPayout.objects.count(), 1)
        self.assertEqual(repeated_payout.sources.count(), 1)
        self.assertEqual(self.account.transactions.count(), 3)

        self.assertEqual(
            self.account.available_balance,
            Decimal("120.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        source = repeated_payout.sources.get()

        self.assertEqual(
            source.deposit_transaction_id,
            self.newer_receipt.deposit_transaction_id,
        )
        self.assertEqual(source.amount, Decimal("40.00"))

    # Проверяем повторное использование ключа с другим способом выплаты:
    # запрос отклоняется, исходная выплата и её источники не меняются.
    def test_payout_rejects_same_key_with_different_method(self):
        payout_data = {
            "account": self.account,
            "amount": Decimal("40.00"),
            "method": PayoutMethod.CASH,
            "operation_key": "account:payout:conflicting-method",
            "created_by": self.manager,
            "comment": "Customer requested a partial payout.",
        }

        payout = record_manual_account_payout(**payout_data)

        payout_data["method"] = PayoutMethod.BANK_TRANSFER

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for different payout data.",
        ):
            record_manual_account_payout(**payout_data)

        self.account.refresh_from_db()
        payout.refresh_from_db()

        self.assertEqual(payout.method, PayoutMethod.CASH)
        self.assertEqual(CustomerPayout.objects.count(), 1)
        self.assertEqual(payout.sources.count(), 1)
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.account.available_balance,
            Decimal("120.00"),
        )

    # Проверяем запрет подтверждения выплаты клиентом:
    # собственный счёт не даёт права регистрировать выдачу денег.
    # Баланс и история остаются без изменений.
    def test_customer_cannot_record_payout(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Only managers and administrators can record payouts.",
        ):
            record_manual_account_payout(
                account=self.account,
                amount=Decimal("40.00"),
                method=PayoutMethod.CASH,
                operation_key="account:payout:forbidden-customer",
                created_by=self.user,
                comment="Customer requested a payout.",
            )

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.account.available_balance,
            Decimal("160.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем подтверждение выплаты администратором:
    # операция разрешена, в истории сохраняются
    # конкретный сотрудник и роль администратора.
    def test_admin_can_record_payout(self):
        admin = create_test_admin()

        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.BANK_TRANSFER,
            operation_key="account:payout:admin",
            created_by=admin,
            comment="Bank payout confirmed by administrator.",
        )

        self.account.refresh_from_db()

        self.assertEqual(payout.method, PayoutMethod.BANK_TRANSFER)
        self.assertEqual(
            payout.account_transaction.created_by_id,
            admin.pk,
        )
        self.assertEqual(
            payout.account_transaction.actor_type,
            AccountTransactionActorType.ADMIN,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("120.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(CustomerPayout.objects.count(), 1)

    # Проверяем запрет выплаты при долге по отгрузкам:
    # свободные деньги не выдаются до погашения долга,
    # документ выплаты не создаётся, балансы не меняются.
    def test_payout_is_forbidden_when_account_has_debt(self):
        record_customer_debt(
            account=self.account,
            amount=Decimal("60.00"),
            operation_key="account:payout:shipment-debt",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Customer account debt must be settled before payout.",
        ):
            record_manual_account_payout(
                account=self.account,
                amount=Decimal("40.00"),
                method=PayoutMethod.CASH,
                operation_key="account:payout:blocked-by-debt",
                created_by=self.manager,
                comment="Customer requested a payout.",
            )

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.account.available_balance,
            Decimal("160.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("60.00"),
        )

    # Проверяем полный откат при ошибке сохранения источника:
    # списание и документ выплаты отменяются вместе,
    # исходный баланс и история восстанавливаются.
    def test_source_creation_failure_rolls_back_entire_payout(self):
        with patch(
            "shop_epower.payments.services.payouts."
            "CustomerPayoutSource.objects.create",
            side_effect=RuntimeError("Source storage failed."),
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Source storage failed.",
            ):
                record_manual_account_payout(
                    account=self.account,
                    amount=Decimal("40.00"),
                    method=PayoutMethod.CASH,
                    operation_key="account:payout:source-failure",
                    created_by=self.manager,
                    comment="Customer requested a partial payout.",
                )

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertFalse(CustomerPayoutSource.objects.exists())
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.account.available_balance,
            Decimal("160.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем запрет отмены поступления, использованного для выплаты:
    # достаточный общий баланс не разрешает отменять источник
    # уже выданных клиенту денег.
    def test_receipt_used_for_payout_cannot_be_cancelled(self):
        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:before-receipt-cancellation",
            created_by=self.manager,
            comment="Money returned to the customer.",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Payment deposit has already been used for a payout.",
        ):
            cancel_manual_order_payment(
                payment=self.newer_receipt,
                operation_key="account:payout:cancel-used-receipt",
                created_by=self.manager,
                comment="Attempt to cancel the original receipt.",
            )

        self.account.refresh_from_db()
        self.newer_receipt.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("120.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.newer_receipt.status, PaymentStatus.PAID)
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(CustomerPayout.objects.count(), 1)
        self.assertEqual(
            payout.sources.get().deposit_transaction_id,
            self.newer_receipt.deposit_transaction_id,
        )

    # Проверяем учёт выплат при последующем назначении заказу:
    # FIFO использует только свободные части поступлений,
    # исключая ранее выданные клиенту деньги.
    def test_order_assignment_excludes_previously_paid_out_funds(self):
        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:before-order-assignment",
            created_by=self.manager,
            comment="Money returned to the customer.",
        )

        third_receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.INVOICE,
            operation_key="account:payout:third-receipt",
            created_by=self.manager,
            comment="Additional bank transfer received.",
        )

        order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("150.00"),
        )

        assignment = assign_order_funds(
            order=order,
            amount=Decimal("150.00"),
            operation_key="account:payout:assignment-after-payout",
            created_by=self.manager,
        )

        self.account.refresh_from_db()

        self.assertCountEqual(
            list(
                assignment.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    self.older_receipt.deposit_transaction_id,
                    Decimal("100.00"),
                ),
                (
                    self.newer_receipt.deposit_transaction_id,
                    Decimal("20.00"),
                ),
                (
                    third_receipt.deposit_transaction_id,
                    Decimal("30.00"),
                ),
            ],
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("70.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(payout.sources.get().amount, Decimal("40.00"))

    # Проверяем изоляцию финансовых счетов:
    # более новое поступление другого клиента не используется,
    # его баланс и история остаются без изменений.
    def test_payout_uses_only_selected_account_deposits(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(
            user=other_user,
        )

        record_manual_account_payment(
            account=other_account,
            amount=Decimal("200.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:payout:other-customer-receipt",
            created_by=self.manager,
            comment="Money received from another customer.",
        )

        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="account:payout:account-isolation",
            created_by=self.manager,
            comment="Customer requested a partial payout.",
        )

        self.account.refresh_from_db()
        other_account.refresh_from_db()

        self.assertEqual(
            payout.account_transaction.account_id,
            self.account.pk,
        )
        self.assertEqual(
            payout.sources.get().deposit_transaction_id,
            self.newer_receipt.deposit_transaction_id,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("120.00"),
        )
        self.assertEqual(
            other_account.available_balance,
            Decimal("200.00"),
        )
        self.assertEqual(other_account.transactions.count(), 1)

    # Проверяем повтор запроса с изменённой суммой:
    # существующий документ не возвращается как успешный результат,
    # исходная выплата, её источники и баланс не меняются.
    def test_payout_rejects_same_key_with_different_amount(self):
        payout_data = {
            "account": self.account,
            "amount": Decimal("40.00"),
            "method": PayoutMethod.CASH,
            "operation_key": "account:payout:conflicting-amount",
            "created_by": self.manager,
            "comment": "Customer requested a partial payout.",
        }

        payout = record_manual_account_payout(**payout_data)

        payout_data["amount"] = Decimal("50.00")

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for different transaction data.",
        ):
            record_manual_account_payout(**payout_data)

        self.account.refresh_from_db()
        payout.refresh_from_db()

        self.assertEqual(payout.amount, Decimal("40.00"))
        self.assertEqual(payout.sources.get().amount, Decimal("40.00"))
        self.assertEqual(CustomerPayout.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.account.available_balance,
            Decimal("120.00"),
        )
