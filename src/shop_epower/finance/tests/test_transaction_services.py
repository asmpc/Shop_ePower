from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import (
    AccountTransaction,
    AccountTransactionActorType,
    AccountTransactionType,
    CustomerAccount,
    CustomerAccountStatus,
)
from shop_epower.finance.services import (
    allocate_customer_funds,
    change_customer_account_status,
    create_personal_customer_account,
    record_customer_debt,
    record_customer_deposit,
    record_customer_refund,
    reverse_customer_transaction,
)


class TestsAccountTransactionServices(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.account = create_personal_customer_account(
            user=self.user,
        )

    # Проверяем пополнение финансового счёта:
    # доступный баланс увеличивается на сумму пополнения,
    # долг не изменяется, а операция сохраняется в истории
    # вместе со снимками итоговых балансов.
    def test_record_customer_deposit_updates_balance_and_creates_transaction(self):
        account_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:test:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
            comment="Customer deposit.",
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            AccountTransaction.objects.count(),
            1,
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
            Decimal("500.00"),
        )
        self.assertEqual(
            account_transaction.debt_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            account_transaction.available_balance_after,
            Decimal("500.00"),
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
        self.assertEqual(
            account_transaction.comment,
            "Customer deposit.",
        )
        self.assertIsNone(
            account_transaction.reversal_of,
        )

    # Проверяем запрет нулевой суммы пополнения:
    # сервис сообщает доменную ошибку, не изменяет баланс
    # и не создаёт финансовую операцию.
    def test_record_customer_deposit_rejects_zero_amount(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Amount must be greater than zero.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=Decimal("0.00"),
                operation_key="deposit:zero:001",
                actor_type=AccountTransactionActorType.CUSTOMER,
                created_by=self.user,
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
        self.assertFalse(
            AccountTransaction.objects.exists(),
        )

    # Проверяем запрет отрицательной суммы пополнения:
    # направление изменения баланса определяет сам сервис,
    # поэтому вызывающий код не может передать отрицательную сумму.
    def test_record_customer_deposit_rejects_negative_amount(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Amount must be greater than zero.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=Decimal("-100.00"),
                operation_key="deposit:negative:001",
                actor_type=AccountTransactionActorType.CUSTOMER,
                created_by=self.user,
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
        self.assertFalse(
            AccountTransaction.objects.exists(),
        )

    # Проверяем идемпотентность одинакового пополнения:
    # повторный вызов с тем же ключом и теми же данными
    # возвращает существующую операцию и не увеличивает баланс повторно.
    def test_record_customer_deposit_returns_existing_transaction_for_same_key(self):
        first_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:idempotent:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
            comment="Idempotent customer deposit.",
        )

        second_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:idempotent:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
            comment="Idempotent customer deposit.",
        )

        self.account.refresh_from_db()

        self.assertEqual(
            second_transaction,
            first_transaction,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            AccountTransaction.objects.count(),
            1,
        )

    # Проверяем конфликт идемпотентного ключа:
    # один operation_key нельзя повторно использовать
    # для пополнения с другой суммой.
    def test_record_customer_deposit_rejects_same_key_with_different_amount(self):
        record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:conflict:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for different transaction data.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=Decimal("600.00"),
                operation_key="deposit:conflict:001",
                actor_type=AccountTransactionActorType.CUSTOMER,
                created_by=self.user,
            )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            AccountTransaction.objects.count(),
            1,
        )

    # Проверяем использование актуального баланса из базы данных:
    # если переданный объект счёта устарел, сервис блокирует и заново
    # загружает счёт, а пополнение применяет к текущему балансу.
    def test_record_customer_deposit_uses_current_database_balance(self):
        CustomerAccount.objects.filter(
            pk=self.account.pk,
        ).update(
            available_balance=Decimal("200.00"),
        )

        # Объект в памяти всё ещё содержит старое значение.
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )

        account_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("50.00"),
            operation_key="deposit:stale-account:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("250.00"),
        )
        self.assertEqual(
            account_transaction.available_delta,
            Decimal("50.00"),
        )
        self.assertEqual(
            account_transaction.available_balance_after,
            Decimal("250.00"),
        )

    # Проверяем атомарность финансовой операции:
    # если обновление баланса счёта завершилось ошибкой,
    # созданная перед этим финансовая транзакция также откатывается.
    def test_record_customer_deposit_rolls_back_when_account_update_fails(self):
        with patch(
            "shop_epower.finance.services.transactions.CustomerAccount.save",
            side_effect=RuntimeError("Account update failed."),
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Account update failed.",
            ):
                record_customer_deposit(
                    account=self.account,
                    amount=Decimal("500.00"),
                    operation_key="deposit:rollback:001",
                    actor_type=AccountTransactionActorType.CUSTOMER,
                    created_by=self.user,
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
        self.assertFalse(
            AccountTransaction.objects.exists(),
        )

    # Проверяем увеличение задолженности клиента:
    # доступный баланс не изменяется, долг увеличивается,
    # а операция сохраняет правильные дельты и итоговые балансы.
    def test_record_customer_debt_updates_debt_and_creates_transaction(self):
        manager = create_test_manager()

        account_transaction = record_customer_debt(
            account=self.account,
            amount=Decimal("800.00"),
            operation_key="debt:test:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
            comment="Customer debt recorded.",
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("800.00"),
        )
        self.assertEqual(
            account_transaction.operation_type,
            AccountTransactionType.DEBT_INCREASE,
        )
        self.assertEqual(
            account_transaction.available_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            account_transaction.debt_delta,
            Decimal("800.00"),
        )
        self.assertEqual(
            account_transaction.available_balance_after,
            Decimal("0.00"),
        )
        self.assertEqual(
            account_transaction.debt_balance_after,
            Decimal("800.00"),
        )

    # Проверяем частичное распределение средств в погашение долга:
    # сумма одновременно вычитается из доступного баланса и долга,
    # а операция сохраняет отрицательные дельты и итоговые балансы.
    def test_allocate_customer_funds_reduces_available_balance_and_debt(self):
        manager = create_test_manager()

        record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:allocation-setup:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        record_customer_debt(
            account=self.account,
            amount=Decimal("800.00"),
            operation_key="debt:allocation-setup:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
        )

        account_transaction = allocate_customer_funds(
            account=self.account,
            amount=Decimal("300.00"),
            operation_key="allocation:test:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
            comment="Partial debt allocation.",
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("200.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            account_transaction.operation_type,
            AccountTransactionType.ALLOCATION,
        )
        self.assertEqual(
            account_transaction.available_delta,
            Decimal("-300.00"),
        )
        self.assertEqual(
            account_transaction.debt_delta,
            Decimal("-300.00"),
        )
        self.assertEqual(
            account_transaction.available_balance_after,
            Decimal("200.00"),
        )
        self.assertEqual(
            account_transaction.debt_balance_after,
            Decimal("500.00"),
        )
        self.assertEqual(
            AccountTransaction.objects.count(),
            3,
        )

    # Проверяем защиту доступного баланса:
    # распределение, превышающее доступные средства,
    # отклоняется без изменения счёта и создания операции.
    def test_allocate_customer_funds_rejects_amount_above_available_balance(self):
        manager = create_test_manager()

        record_customer_deposit(
            account=self.account,
            amount=Decimal("200.00"),
            operation_key="deposit:available-limit-setup:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        record_customer_debt(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="debt:available-limit-setup:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Resulting available balance cannot be negative.",
        ):
            allocate_customer_funds(
                account=self.account,
                amount=Decimal("300.00"),
                operation_key="allocation:available-limit:001",
                actor_type=AccountTransactionActorType.MANAGER,
                created_by=manager,
            )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("200.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            AccountTransaction.objects.count(),
            2,
        )

    # Проверяем защиту баланса задолженности:
    # распределение, превышающее текущий долг,
    # отклоняется без изменения счёта и создания операции.
    def test_allocate_customer_funds_rejects_amount_above_debt_balance(self):
        manager = create_test_manager()

        record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:debt-limit-setup:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        record_customer_debt(
            account=self.account,
            amount=Decimal("200.00"),
            operation_key="debt:debt-limit-setup:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Resulting debt balance cannot be negative.",
        ):
            allocate_customer_funds(
                account=self.account,
                amount=Decimal("300.00"),
                operation_key="allocation:debt-limit:001",
                actor_type=AccountTransactionActorType.MANAGER,
                created_by=manager,
            )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("200.00"),
        )
        self.assertEqual(
            AccountTransaction.objects.count(),
            2,
        )

    # Проверяем возврат средств на финансовый счёт:
    # доступный баланс увеличивается на сумму возврата,
    # долг не изменяется, а операция получает тип REFUND.
    def test_record_customer_refund_adds_funds_to_available_balance(self):
        manager = create_test_manager()

        account_transaction = record_customer_refund(
            account=self.account,
            amount=Decimal("250.00"),
            operation_key="refund:test:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
            comment="Refund to customer balance.",
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("250.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            account_transaction.operation_type,
            AccountTransactionType.REFUND,
        )
        self.assertEqual(
            account_transaction.available_delta,
            Decimal("250.00"),
        )
        self.assertEqual(
            account_transaction.debt_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            account_transaction.available_balance_after,
            Decimal("250.00"),
        )
        self.assertEqual(
            account_transaction.debt_balance_after,
            Decimal("0.00"),
        )

    # Проверяем обратную операцию для пополнения:
    # reversal использует противоположные дельты,
    # возвращает баланс в исходное состояние
    # и сохраняет ссылку на отменённую операцию.
    def test_reverse_customer_transaction_reverses_deposit(self):
        original_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:reversal-setup:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        admin = create_test_admin()

        reversal_transaction = reverse_customer_transaction(
            original_transaction=original_transaction,
            operation_key="reversal:deposit:001",
            actor_type=AccountTransactionActorType.ADMIN,
            created_by=admin,
            comment="Deposit recorded by mistake.",
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
            AccountTransaction.objects.count(),
            2,
        )
        self.assertEqual(
            reversal_transaction.operation_type,
            AccountTransactionType.REVERSAL,
        )
        self.assertEqual(
            reversal_transaction.available_delta,
            Decimal("-500.00"),
        )
        self.assertEqual(
            reversal_transaction.debt_delta,
            Decimal("0.00"),
        )
        self.assertEqual(
            reversal_transaction.available_balance_after,
            Decimal("0.00"),
        )
        self.assertEqual(
            reversal_transaction.debt_balance_after,
            Decimal("0.00"),
        )
        self.assertEqual(
            reversal_transaction.currency_snapshot,
            original_transaction.currency_snapshot,
        )
        self.assertEqual(
            reversal_transaction.reversal_of,
            original_transaction,
        )

    # Проверяем обязательность комментария для reversal:
    # пустая причина не отменяет исходную операцию
    # и не создаёт новую финансовую запись.
    def test_reverse_customer_transaction_requires_comment(self):
        original_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:reversal-comment-setup:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        admin = create_test_admin()

        with self.assertRaisesMessage(
            ValidationError,
            "Reversal comment is required.",
        ):
            reverse_customer_transaction(
                original_transaction=original_transaction,
                operation_key="reversal:blank-comment:001",
                actor_type=AccountTransactionActorType.ADMIN,
                created_by=admin,
                comment="   ",
            )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            AccountTransaction.objects.count(),
            1,
        )
        self.assertFalse(
            hasattr(
                original_transaction,
                "reversal",
            ),
        )

    # Проверяем запрет повторной отмены:
    # после создания первого reversal другая операция reversal
    # для той же исходной транзакции не создаётся.
    def test_reverse_customer_transaction_rejects_already_reversed_transaction(self):
        original_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:double-reversal-setup:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        admin = create_test_admin()

        reverse_customer_transaction(
            original_transaction=original_transaction,
            operation_key="reversal:first:001",
            actor_type=AccountTransactionActorType.ADMIN,
            created_by=admin,
            comment="First reversal.",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Transaction has already been reversed.",
        ):
            reverse_customer_transaction(
                original_transaction=original_transaction,
                operation_key="reversal:second:001",
                actor_type=AccountTransactionActorType.ADMIN,
                created_by=admin,
                comment="Attempting a second reversal.",
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
            AccountTransaction.objects.count(),
            2,
        )

    # Проверяем запрет отмены другого reversal:
    # обратная операция не может быть исходной операцией
    # для следующего reversal.
    def test_reverse_customer_transaction_rejects_reversal_transaction(self):
        original_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:reverse-reversal-setup:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        admin = create_test_admin()

        first_reversal = reverse_customer_transaction(
            original_transaction=original_transaction,
            operation_key="reversal:reverse-reversal-setup:001",
            actor_type=AccountTransactionActorType.ADMIN,
            created_by=admin,
            comment="Reverse the original deposit.",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "A reversal transaction cannot be reversed.",
        ):
            reverse_customer_transaction(
                original_transaction=first_reversal,
                operation_key="reversal:of-reversal:001",
                actor_type=AccountTransactionActorType.ADMIN,
                created_by=admin,
                comment="Attempting to reverse a reversal.",
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
            AccountTransaction.objects.count(),
            2,
        )

    # Проверяем обязательность инициатора для человеческой операции:
    # actor_type=CUSTOMER без created_by отклоняется,
    # баланс и финансовая история не изменяются.
    def test_record_customer_deposit_requires_created_by_for_human_actor(self):
        with self.assertRaisesMessage(
            ValidationError,
            "created_by is required for human financial operations.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=Decimal("500.00"),
                operation_key="deposit:missing-actor:001",
                actor_type=AccountTransactionActorType.CUSTOMER,
                created_by=None,
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
        self.assertFalse(
            AccountTransaction.objects.exists(),
        )

    # Проверяем автоматическую финансовую операцию:
    # actor_type=SYSTEM разрешает отсутствие created_by,
    # при этом тип инициатора сохраняется в истории.
    def test_record_customer_deposit_allows_system_actor_without_created_by(self):
        account_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:system:001",
            actor_type=AccountTransactionActorType.SYSTEM,
            created_by=None,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            account_transaction.actor_type,
            AccountTransactionActorType.SYSTEM,
        )
        self.assertIsNone(
            account_transaction.created_by,
        )

    # Проверяем допустимость типа инициатора:
    # неизвестный actor_type не сохраняется
    # и не изменяет финансовое состояние счёта.
    def test_record_customer_deposit_rejects_unknown_actor_type(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Unsupported financial operation actor type.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=Decimal("500.00"),
                operation_key="deposit:unknown-actor:001",
                actor_type="robot",
                created_by=self.user,
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
        self.assertFalse(
            AccountTransaction.objects.exists(),
        )

    # Проверяем валюту обратной операции:
    # если валюта счёта после исходной операции изменилась,
    # сервис не создаёт reversal с другой валютой.
    def test_reverse_customer_transaction_rejects_currency_mismatch(self):
        original_transaction = record_customer_deposit(
            account=self.account,
            amount=Decimal("500.00"),
            operation_key="deposit:currency-mismatch:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        admin = create_test_admin()
        other_currency = (
            "USD" if original_transaction.currency_snapshot != "USD" else "BYN"
        )

        CustomerAccount.objects.filter(pk=self.account.pk).update(
            currency=other_currency,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Original transaction currency does not match account currency.",
        ):
            reverse_customer_transaction(
                original_transaction=original_transaction,
                operation_key="reversal:currency-mismatch:001",
                actor_type=AccountTransactionActorType.ADMIN,
                created_by=admin,
                comment="Checking currency consistency.",
            )

        self.account.refresh_from_db()

        self.assertEqual(self.account.available_balance, Decimal("500.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(AccountTransaction.objects.count(), 1)

    # Проверяем, что неактивному счёту нельзя начислить новый долг.
    def test_record_customer_debt_rejects_inactive_account(self):
        manager = create_test_manager()
        change_customer_account_status(
            account=self.account,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Account deactivated.",
            changed_by=manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Inactive customer account cannot receive new debt.",
        ):
            record_customer_debt(
                account=self.account,
                amount=Decimal("200.00"),
                operation_key="debt:inactive-account:001",
                actor_type=AccountTransactionActorType.MANAGER,
                created_by=manager,
            )

        self.account.refresh_from_db()

        self.assertEqual(self.account.status, CustomerAccountStatus.INACTIVE)
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertFalse(AccountTransaction.objects.exists())

    # Проверяем, что сервис не принимает сумму с долями меньше копейки.
    def test_record_customer_deposit_rejects_more_than_two_decimal_places(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Amount must have no more than two decimal places.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=Decimal("10.001"),
                operation_key="deposit:excess-precision:001",
                actor_type=AccountTransactionActorType.CUSTOMER,
                created_by=self.user,
            )

        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertFalse(AccountTransaction.objects.exists())

    # Проверяем, что финансовый сервис не принимает float.
    def test_record_customer_deposit_rejects_float_amount(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Amount must be a Decimal.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=10.5,
                operation_key="deposit:float:001",
                actor_type=AccountTransactionActorType.CUSTOMER,
                created_by=self.user,
            )

        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertFalse(AccountTransaction.objects.exists())

    # Проверяем, что ключ из одних пробелов нельзя использовать для операции.
    def test_record_customer_deposit_rejects_blank_operation_key(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is required.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=Decimal("10.00"),
                operation_key="   ",
                actor_type=AccountTransactionActorType.CUSTOMER,
                created_by=self.user,
            )

        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertFalse(AccountTransaction.objects.exists())

    # Проверяем, что NaN и бесконечность не принимаются как денежные суммы.
    def test_record_customer_deposit_rejects_non_finite_amount(self):
        for invalid_amount in (Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(amount=str(invalid_amount)):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Amount must be finite.",
                ):
                    record_customer_deposit(
                        account=self.account,
                        amount=invalid_amount,
                        operation_key=f"deposit:non-finite:{invalid_amount}",
                        actor_type=AccountTransactionActorType.CUSTOMER,
                        created_by=self.user,
                    )

        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertFalse(AccountTransaction.objects.exists())

    # Средства взаимозаменяемы: более позднее пополнение позволяет
    # отменить раннее, если итоговый остаток не станет отрицательным.
    def test_reverse_deposit_after_allocation_and_later_deposit(self):
        manager = create_test_manager()
        admin = create_test_admin()

        first_deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="deposit:fungible:first",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        record_customer_debt(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="debt:fungible",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
        )
        allocate_customer_funds(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="allocation:fungible",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
        )
        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="deposit:fungible:second",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )

        reversal = reverse_customer_transaction(
            original_transaction=first_deposit,
            operation_key="reversal:fungible:first",
            actor_type=AccountTransactionActorType.ADMIN,
            created_by=admin,
            comment="Correcting the first deposit.",
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(reversal.reversal_of, first_deposit)
        self.assertEqual(AccountTransaction.objects.count(), 5)

    # Если запись в журнал не создана, остаток счёта не меняется.
    def test_record_customer_deposit_keeps_balance_when_transaction_creation_fails(
        self,
    ):
        with patch.object(
            AccountTransaction.objects,
            "create",
            side_effect=RuntimeError("Transaction creation failed."),
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Transaction creation failed.",
            ):
                record_customer_deposit(
                    account=self.account,
                    amount=Decimal("100.00"),
                    operation_key="deposit:create-failure:001",
                    actor_type=AccountTransactionActorType.CUSTOMER,
                    created_by=self.user,
                )

        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertFalse(AccountTransaction.objects.exists())

    # Сервис не записывает деньги на счёт в другой валюте.
    def test_record_customer_deposit_rejects_account_with_wrong_currency(self):
        other_currency = "USD" if self.account.currency != "USD" else "BYN"

        # Имитируем ошибочное изменение данных в БД.
        CustomerAccount.objects.filter(pk=self.account.pk).update(
            currency=other_currency,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Account currency does not match deployment base currency.",
        ):
            record_customer_deposit(
                account=self.account,
                amount=Decimal("100.00"),
                operation_key="deposit:wrong-currency:001",
                actor_type=AccountTransactionActorType.CUSTOMER,
                created_by=self.user,
            )

        self.account.refresh_from_db()
        self.assertEqual(self.account.currency, other_currency)
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertFalse(AccountTransaction.objects.exists())

    # Отмена пополнения запрещена, если после неё остаток станет отрицательным.
    def test_reverse_deposit_rejects_negative_available_balance(self):
        manager = create_test_manager()

        deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="deposit:reversal-limit:001",
            actor_type=AccountTransactionActorType.CUSTOMER,
            created_by=self.user,
        )
        record_customer_debt(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="debt:reversal-limit:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
        )
        allocate_customer_funds(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="allocation:reversal-limit:001",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Resulting available balance cannot be negative.",
        ):
            reverse_customer_transaction(
                original_transaction=deposit,
                operation_key="reversal:insufficient-funds:001",
                actor_type=AccountTransactionActorType.MANAGER,
                created_by=manager,
                comment="Attempt to reverse spent funds.",
            )

        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(AccountTransaction.objects.count(), 3)
