from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.finance.models import (
    AccountTransaction,
    AccountTransactionActorType,
)
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_deposit,
)


class TestsAccountTransactionConcurrency(TransactionTestCase):
    def setUp(self):
        user = create_test_user()
        self.account = create_personal_customer_account(user=user)

    # Два запроса начинают работу вместе и не теряют ни одно пополнение.
    def test_concurrent_deposits_preserve_both_balance_updates(self):
        start = Barrier(3)

        def deposit(amount, operation_key):
            close_old_connections()
            try:
                start.wait(timeout=10)
                return record_customer_deposit(
                    account=self.account,
                    amount=amount,
                    operation_key=operation_key,
                    actor_type=AccountTransactionActorType.SYSTEM,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                deposit, Decimal("100.00"), "deposit:concurrent:first"
            )
            second = executor.submit(
                deposit, Decimal("200.00"), "deposit:concurrent:second"
            )
            start.wait(timeout=10)

            first.result(timeout=30)
            second.result(timeout=30)

        self.account.refresh_from_db()
        transactions = list(
            AccountTransaction.objects.filter(
                account=self.account,
            ).order_by("pk")
        )

        self.assertEqual(self.account.available_balance, Decimal("300.00"))
        self.assertEqual(len(transactions), 2)
        self.assertEqual(
            sorted(item.available_delta for item in transactions),
            [Decimal("100.00"), Decimal("200.00")],
        )
        self.assertEqual(
            transactions[-1].available_balance_after,
            Decimal("300.00"),
        )

    # Два одинаковых запроса дают одну операцию и одно зачисление.
    def test_concurrent_duplicate_deposit_is_applied_once(self):
        start = Barrier(3)

        def deposit():
            close_old_connections()
            try:
                start.wait(timeout=10)
                return record_customer_deposit(
                    account=self.account,
                    amount=Decimal("100.00"),
                    operation_key="deposit:concurrent:duplicate",
                    actor_type=AccountTransactionActorType.SYSTEM,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(deposit)
            second = executor.submit(deposit)
            start.wait(timeout=10)

            first_transaction = first.result(timeout=30)
            second_transaction = second.result(timeout=30)

        self.account.refresh_from_db()

        self.assertEqual(first_transaction.pk, second_transaction.pk)
        self.assertEqual(self.account.available_balance, Decimal("100.00"))
        self.assertEqual(
            AccountTransaction.objects.filter(account=self.account).count(),
            1,
        )
