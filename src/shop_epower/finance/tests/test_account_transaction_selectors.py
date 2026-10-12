from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.finance.models import AccountTransactionActorType
from shop_epower.finance.selectors import (
    get_account_transactions,
    get_financial_transactions_for_staff,
)
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_deposit,
)


class TestsAccountTransactionSelectors(TestCase):
    # История одного счёта не содержит операции другого счёта.
    def test_get_account_transactions_returns_only_selected_account(self):
        customer = create_test_user()
        other_customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        other_account = create_personal_customer_account(user=other_customer)

        transaction = record_customer_deposit(
            account=account,
            amount=Decimal("100.00"),
            operation_key="account-history:own:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        record_customer_deposit(
            account=other_account,
            amount=Decimal("200.00"),
            operation_key="account-history:other:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        self.assertEqual(
            list(get_account_transactions(account=account)),
            [transaction],
        )

    # Общий журнал не загружается без поиска;
    # часть ключа находит нужную операцию среди разных счетов.
    def test_staff_journal_requires_search_and_finds_operation_key(self):
        first_customer = create_test_user()
        second_customer = create_test_user()
        first_account = create_personal_customer_account(user=first_customer)
        second_account = create_personal_customer_account(user=second_customer)

        target = record_customer_deposit(
            account=first_account,
            amount=Decimal("100.00"),
            operation_key="journal:target:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        record_customer_deposit(
            account=second_account,
            amount=Decimal("200.00"),
            operation_key="journal:other:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        self.assertEqual(
            list(get_financial_transactions_for_staff()),
            [],
        )
        self.assertEqual(
            list(get_financial_transactions_for_staff(operation_key="target")),
            [target],
        )
