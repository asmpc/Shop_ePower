from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import (
    AccountTransactionActorType,
    AccountTransactionType,
)
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_debt,
    record_customer_deposit,
    record_customer_payout,
)


class TestsCustomerPayoutServices(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )

        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="payout:test:initial-deposit",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

    # Проверяем частичный фактический возврат:
    # свободный баланс уменьшается, долг не меняется,
    # а расходная операция сохраняет сумму, автора и причину.
    def test_payout_reduces_available_balance_and_records_transaction(self):
        payout = record_customer_payout(
            account=self.account,
            amount=Decimal("40.00"),
            operation_key="payout:test:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
            comment="Customer requested a partial payout.",
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

        self.assertEqual(payout.account, self.account)
        self.assertEqual(
            payout.operation_type,
            AccountTransactionType.PAYOUT,
        )
        self.assertEqual(payout.available_delta, Decimal("-40.00"))
        self.assertEqual(payout.debt_delta, Decimal("0.00"))
        self.assertEqual(
            payout.available_balance_after,
            Decimal("60.00"),
        )
        self.assertEqual(
            payout.debt_balance_after,
            Decimal("0.00"),
        )
        self.assertEqual(
            payout.currency_snapshot,
            self.account.currency,
        )
        self.assertEqual(payout.operation_key, "payout:test:001")
        self.assertEqual(
            payout.actor_type,
            AccountTransactionActorType.MANAGER,
        )
        self.assertEqual(payout.created_by, self.manager)
        self.assertEqual(
            payout.comment,
            "Customer requested a partial payout.",
        )

    # Проверяем запрет фактического возврата при долге:
    # достаточный свободный баланс не разрешает выплату,
    # оба баланса и история операций остаются без изменений.
    def test_payout_is_forbidden_when_account_has_debt(self):
        record_customer_debt(
            account=self.account,
            amount=Decimal("60.00"),
            operation_key="payout:test:shipment-debt",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Customer account debt must be settled before payout.",
        ):
            record_customer_payout(
                account=self.account,
                amount=Decimal("40.00"),
                operation_key="payout:test:blocked-by-debt",
                actor_type=AccountTransactionActorType.MANAGER,
                created_by=self.manager,
                comment="Customer requested a partial payout.",
            )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("60.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

    # Проверяем запрет выплаты сверх свободного остатка:
    # операция отклоняется целиком, баланс и история не меняются.
    def test_payout_cannot_exceed_available_balance(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Resulting available balance cannot be negative.",
        ):
            record_customer_payout(
                account=self.account,
                amount=Decimal("100.01"),
                operation_key="payout:test:insufficient-balance",
                actor_type=AccountTransactionActorType.MANAGER,
                created_by=self.manager,
                comment="Customer requested a payout.",
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

    # Проверяем обязательную причину выплаты:
    # пустая строка и строка из пробелов отклоняются,
    # свободный баланс и история остаются без изменений.
    def test_payout_requires_reason(self):
        for comment in ("", "   "):
            with self.subTest(comment=comment):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Payout reason is required.",
                ):
                    record_customer_payout(
                        account=self.account,
                        amount=Decimal("40.00"),
                        operation_key="payout:test:missing-reason",
                        actor_type=AccountTransactionActorType.MANAGER,
                        created_by=self.manager,
                        comment=comment,
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

    # Проверяем повтор запроса с тем же ключом и данными:
    # возвращается исходная операция, повторного списания нет.
    def test_repeated_payout_does_not_debit_balance_twice(self):
        payout_data = {
            "account": self.account,
            "amount": Decimal("40.00"),
            "operation_key": "payout:test:repeated-request",
            "actor_type": AccountTransactionActorType.MANAGER,
            "created_by": self.manager,
            "comment": "Customer requested a partial payout.",
        }

        first_payout = record_customer_payout(**payout_data)
        repeated_payout = record_customer_payout(**payout_data)

        self.account.refresh_from_db()

        self.assertEqual(repeated_payout.pk, first_payout.pk)
        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

    # Проверяем повтор выполненной выплаты после появления долга:
    # сервис возвращает прежнюю операцию без нового списания,
    # а возникший позднее долг остаётся без изменений.
    def test_repeated_payout_returns_original_transaction_after_debt_appears(self):
        payout_data = {
            "account": self.account,
            "amount": Decimal("40.00"),
            "operation_key": "payout:test:repeat-after-debt",
            "actor_type": AccountTransactionActorType.MANAGER,
            "created_by": self.manager,
            "comment": "Customer requested a partial payout.",
        }

        first_payout = record_customer_payout(**payout_data)

        record_customer_debt(
            account=self.account,
            amount=Decimal("20.00"),
            operation_key="payout:test:later-shipment-debt",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

        repeated_payout = record_customer_payout(**payout_data)

        self.account.refresh_from_db()

        self.assertEqual(repeated_payout.pk, first_payout.pk)
        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("20.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            repeated_payout.debt_balance_after,
            Decimal("0.00"),
        )

    # Проверяем повторное использование ключа с другой суммой:
    # сервис отклоняет запрос, исходная выплата и баланс не меняются.
    def test_payout_rejects_same_key_with_different_amount(self):
        payout_data = {
            "account": self.account,
            "amount": Decimal("40.00"),
            "operation_key": "payout:test:conflicting-amount",
            "actor_type": AccountTransactionActorType.MANAGER,
            "created_by": self.manager,
            "comment": "Customer requested a partial payout.",
        }

        first_payout = record_customer_payout(**payout_data)

        payout_data["amount"] = Decimal("50.00")

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for different transaction data.",
        ):
            record_customer_payout(**payout_data)

        self.account.refresh_from_db()
        first_payout.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            first_payout.available_delta,
            Decimal("-40.00"),
        )
