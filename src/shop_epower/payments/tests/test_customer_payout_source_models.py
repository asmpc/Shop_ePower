from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import AccountTransactionActorType
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_deposit,
    record_customer_payout,
)
from shop_epower.payments.models import (
    CustomerPayout,
    CustomerPayoutSource,
    PayoutMethod,
)


class TestsCustomerPayoutSourceModels(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )

        self.deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="payout:source:model:deposit",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

        payout_transaction = record_customer_payout(
            account=self.account,
            amount=Decimal("40.00"),
            operation_key="payout:source:model:transaction",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
            comment="Customer requested a partial payout.",
        )

        self.payout = CustomerPayout.objects.create(
            account_transaction=payout_transaction,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
        )

    # Проверяем уникальность источника внутри выплаты:
    # одно поступление нельзя записать дважды для одной выплаты.
    def test_same_deposit_cannot_be_linked_to_payout_twice(self):
        CustomerPayoutSource.objects.create(
            payout=self.payout,
            deposit_transaction=self.deposit,
            amount=Decimal("40.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerPayoutSource.objects.create(
                    payout=self.payout,
                    deposit_transaction=self.deposit,
                    amount=Decimal("40.00"),
                )

        self.assertEqual(CustomerPayoutSource.objects.count(), 1)

    # Проверяем запрет нулевой суммы источника:
    # запись должна отражать реально использованную часть поступления.
    def test_payout_source_rejects_zero_amount(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerPayoutSource.objects.create(
                    payout=self.payout,
                    deposit_transaction=self.deposit,
                    amount=Decimal("0.00"),
                )

        self.assertFalse(CustomerPayoutSource.objects.exists())

    # Проверяем запрет отрицательной суммы источника:
    # использованная часть поступления должна быть положительной.
    def test_payout_source_rejects_negative_amount(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerPayoutSource.objects.create(
                    payout=self.payout,
                    deposit_transaction=self.deposit,
                    amount=Decimal("-10.00"),
                )

        self.assertFalse(CustomerPayoutSource.objects.exists())
