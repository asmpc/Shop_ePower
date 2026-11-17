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
    PayoutMethod,
)


class TestsCustomerPayoutModels(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )

        record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="payout:model:deposit",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

        self.payout_transaction = record_customer_payout(
            account=self.account,
            amount=Decimal("40.00"),
            operation_key="payout:model:transaction",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
            comment="Customer requested a partial payout.",
        )

    # Проверяем уникальность связи с расходной операцией:
    # одна операция списания не может подтверждать две выплаты,
    # даже если для второй указан другой способ выдачи денег.
    def test_payout_transaction_cannot_be_linked_twice(self):
        CustomerPayout.objects.create(
            account_transaction=self.payout_transaction,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerPayout.objects.create(
                    account_transaction=self.payout_transaction,
                    amount=Decimal("40.00"),
                    method=PayoutMethod.BANK_TRANSFER,
                )

        self.assertEqual(CustomerPayout.objects.count(), 1)

    # Проверяем запрет нулевой суммы выплаты:
    # база данных отклоняет запись, выплата не сохраняется.
    def test_payout_rejects_zero_amount(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerPayout.objects.create(
                    account_transaction=self.payout_transaction,
                    amount=Decimal("0.00"),
                    method=PayoutMethod.CASH,
                )

        self.assertFalse(CustomerPayout.objects.exists())

    # Проверяем запрет отрицательной суммы выплаты:
    # сумма документа должна быть положительной,
    # направление списания задаётся финансовой операцией.
    def test_payout_rejects_negative_amount(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerPayout.objects.create(
                    account_transaction=self.payout_transaction,
                    amount=Decimal("-10.00"),
                    method=PayoutMethod.CASH,
                )

        self.assertFalse(CustomerPayout.objects.exists())