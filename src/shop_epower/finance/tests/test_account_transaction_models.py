from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.finance.models import (
    AccountTransaction,
    AccountTransactionActorType,
    AccountTransactionType,
    CustomerAccount,
    CustomerAccountType,
)


class TestsAccountTransactionModel(TestCase):
    def setUp(self):
        self.user = create_test_user(
            email="finance-transaction-client@test.com",
            username="finance-transaction-client",
            password="testpass123",
        )

        self.account = CustomerAccount.objects.create(
            user=self.user,
            account_type=CustomerAccountType.PERSONAL,
        )

    # Проверяем создание записи финансового реестра:
    # операция пополнения хранит изменение доступных средств,
    # итоговые балансы, валюту, ключ идемпотентности и инициатора.
    def test_deposit_transaction_can_be_created(self):
        account_transaction = AccountTransaction.objects.create(
            account=self.account,
            operation_type=AccountTransactionType.DEPOSIT,
            available_delta=Decimal("100.00"),
            debt_delta=Decimal("0.00"),
            available_balance_after=Decimal("100.00"),
            debt_balance_after=Decimal("0.00"),
            currency_snapshot=self.account.currency,
            operation_key="deposit:test:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )

        self.assertEqual(
            account_transaction.account,
            self.account,
        )
        self.assertEqual(
            account_transaction.operation_type,
            AccountTransactionType.DEPOSIT,
        )
        self.assertEqual(
            account_transaction.available_delta,
            Decimal("100.00"),
        )
        self.assertEqual(
            account_transaction.debt_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            account_transaction.available_balance_after,
            Decimal("100.00"),
        )
        self.assertEqual(
            account_transaction.debt_balance_after,
            Decimal("0.00"),
        )
        self.assertEqual(
            account_transaction.currency_snapshot,
            self.account.currency,
        )
        self.assertEqual(
            account_transaction.operation_key,
            "deposit:test:001",
        )
        self.assertEqual(
            account_transaction.actor_type,
            AccountTransactionActorType.CUSTOMER,
        )
        self.assertEqual(
            account_transaction.created_by,
            self.user,
        )
        self.assertIsNone(
            account_transaction.reversal_of,
        )
        self.assertEqual(
            account_transaction.comment,
            "",
        )
        self.assertIsNotNone(
            account_transaction.created_at,
        )

    # Проверяем защиту от повторной обработки команды:
    # две финансовые операции не могут иметь одинаковый operation_key.
    def test_operation_key_must_be_unique(self):
        AccountTransaction.objects.create(
            account=self.account,
            operation_type=AccountTransactionType.DEPOSIT,
            available_delta=Decimal("100.00"),
            debt_delta=Decimal("0.00"),
            available_balance_after=Decimal("100.00"),
            debt_balance_after=Decimal("0.00"),
            currency_snapshot=self.account.currency,
            operation_key="deposit:duplicate:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccountTransaction.objects.create(
                    account=self.account,
                    operation_type=AccountTransactionType.DEPOSIT,
                    available_delta=Decimal("100.00"),
                    debt_delta=Decimal("0.00"),
                    available_balance_after=Decimal("200.00"),
                    debt_balance_after=Decimal("0.00"),
                    currency_snapshot=self.account.currency,
                    operation_key="deposit:duplicate:001",
                    actor_type=AccountTransactionActorType.SYSTEM,
                )

    # Проверяем финансовый инвариант записи реестра:
    # доступный баланс после операции не может быть отрицательным.
    def test_available_balance_after_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccountTransaction.objects.create(
                    account=self.account,
                    operation_type=AccountTransactionType.ALLOCATION,
                    available_delta=Decimal("-0.01"),
                    debt_delta=Decimal("0.00"),
                    available_balance_after=Decimal("-0.01"),
                    debt_balance_after=Decimal("0.00"),
                    currency_snapshot=self.account.currency,
                    operation_key="allocation:negative-available:001",
                    actor_type=AccountTransactionActorType.SYSTEM,
                )

    # Проверяем финансовый инвариант записи реестра:
    # остаток долга после операции не может быть отрицательным.
    def test_debt_balance_after_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccountTransaction.objects.create(
                    account=self.account,
                    operation_type=AccountTransactionType.ALLOCATION,
                    available_delta=Decimal("0.00"),
                    debt_delta=Decimal("-0.01"),
                    available_balance_after=Decimal("0.00"),
                    debt_balance_after=Decimal("-0.01"),
                    currency_snapshot=self.account.currency,
                    operation_key="allocation:negative-debt:001",
                    actor_type=AccountTransactionActorType.SYSTEM,
                )

    # Проверяем содержательность записи реестра:
    # операция не может одновременно иметь нулевые изменения
    # доступных средств и долга.
    def test_transaction_cannot_have_two_zero_deltas(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccountTransaction.objects.create(
                    account=self.account,
                    operation_type=AccountTransactionType.DEPOSIT,
                    available_delta=Decimal("0.00"),
                    debt_delta=Decimal("0.00"),
                    available_balance_after=Decimal("0.00"),
                    debt_balance_after=Decimal("0.00"),
                    currency_snapshot=self.account.currency,
                    operation_key="deposit:zero-deltas:001",
                    actor_type=AccountTransactionActorType.SYSTEM,
                )

    # Проверяем защиту от повторной отмены:
    # одна исходная финансовая операция может иметь
    # не более одной обратной операции.
    def test_transaction_can_have_only_one_reversal(self):
        original_transaction = AccountTransaction.objects.create(
            account=self.account,
            operation_type=AccountTransactionType.DEPOSIT,
            available_delta=Decimal("100.00"),
            debt_delta=Decimal("0.00"),
            available_balance_after=Decimal("100.00"),
            debt_balance_after=Decimal("0.00"),
            currency_snapshot=self.account.currency,
            operation_key="deposit:reversal-source:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        AccountTransaction.objects.create(
            account=self.account,
            operation_type=AccountTransactionType.REVERSAL,
            available_delta=Decimal("-100.00"),
            debt_delta=Decimal("0.00"),
            available_balance_after=Decimal("0.00"),
            debt_balance_after=Decimal("0.00"),
            currency_snapshot=self.account.currency,
            operation_key="reversal:first:001",
            reversal_of=original_transaction,
            comment="Correcting the original deposit.",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccountTransaction.objects.create(
                    account=self.account,
                    operation_type=AccountTransactionType.REVERSAL,
                    available_delta=Decimal("-100.00"),
                    debt_delta=Decimal("0.00"),
                    available_balance_after=Decimal("0.00"),
                    debt_balance_after=Decimal("0.00"),
                    currency_snapshot=self.account.currency,
                    operation_key="reversal:second:001",
                    reversal_of=original_transaction,
                    comment="Attempting a second reversal.",
                    actor_type=AccountTransactionActorType.SYSTEM,
                )

    # Проверяем, что для получения операций счёта
    # в хронологическом порядке определён составной индекс.
    def test_account_transaction_has_account_created_at_index(self):
        index_fields = [
            tuple(index.fields) for index in AccountTransaction._meta.indexes
        ]

        self.assertIn(
            ("account", "created_at"),
            index_fields,
        )

    # Проверяем, что для фильтрации финансовых операций
    # по типу определён отдельный индекс.
    def test_account_transaction_has_operation_type_index(self):
        index_fields = [
            tuple(index.fields) for index in AccountTransaction._meta.indexes
        ]

        self.assertIn(
            ("operation_type",),
            index_fields,
        )

    # Проверяем, что для фильтрации финансовых операций
    # по типу инициатора определён отдельный индекс.
    def test_account_transaction_has_actor_type_index(self):
        index_fields = [
            tuple(index.fields) for index in AccountTransaction._meta.indexes
        ]

        self.assertIn(
            ("actor_type",),
            index_fields,
        )
