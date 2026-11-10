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
)
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)


class TestsAccountReceiptModels(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

    # Поступление может существовать без заказа.
    # Связь с финансовым счётом сохраняется через пополнение.
    # У клиента при этом нет ни одного заказа.
    def test_receipt_can_exist_without_order(self):
        deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key="account:receipt:model",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

        payment = Payment.objects.create(
            order=None,
            deposit_transaction=deposit,
            method=PaymentMethod.ON_RECEIPT,
            provider=PaymentProvider.MANUAL,
            status=PaymentStatus.PAID,
            amount=Decimal("100.00"),
            currency_snapshot=self.account.currency,
        )

        payment.refresh_from_db()

        self.assertIsNone(payment.order_id)
        self.assertEqual(payment.deposit_transaction_id, deposit.pk)
        self.assertEqual(
            payment.deposit_transaction.account_id,
            self.account.pk,
        )
        self.assertFalse(self.user.orders.exists())

    # Платёж должен быть связан с заказом или пополнением счёта.
    # Запись без обеих связей запрещена на уровне базы данных.
    def test_payment_requires_order_or_deposit(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.create(
                    order=None,
                    deposit_transaction=None,
                    method=PaymentMethod.ON_RECEIPT,
                    provider=PaymentProvider.MANUAL,
                    status=PaymentStatus.PAID,
                    amount=Decimal("100.00"),
                    currency_snapshot=self.account.currency,
                )

        self.assertFalse(Payment.objects.exists())
