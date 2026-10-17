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
    AccountTransactionActorType,
    AccountTransactionType,
)
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_deposit,
)
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import (
    record_manual_order_payment,
    reset_payment_to_pending,
)


class TestsPaymentReceiptServices(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
            payment_method=PaymentMethod.ON_RECEIPT,
        )

    # Проверяем регистрацию фактически полученных денег в офисе:
    # менеджер создаёт оплаченный платёж на полученную сумму,
    # а финансовый журнал и доступный баланс отражают пополнение.
    # Долг, статус заказа и распределение денег не меняются.
    def test_office_receipt_creates_paid_payment_and_credits_account(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("40.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="office:receipt:001",
            created_by=self.manager,
            comment="Payment received in the office.",
        )

        payment.refresh_from_db()

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(payment.order, self.order)
        self.assertEqual(payment.amount, Decimal("40.00"))
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.method, PaymentMethod.ON_RECEIPT)
        self.assertEqual(payment.provider, PaymentProvider.MANUAL)
        self.assertEqual(payment.currency_snapshot, self.account.currency)

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        self.assertEqual(self.account.transactions.count(), 1)

        deposit = self.account.transactions.get()

        self.assertEqual(payment.deposit_transaction, deposit)

        self.assertEqual(deposit.operation_type, AccountTransactionType.DEPOSIT)
        self.assertEqual(deposit.operation_key, "office:receipt:001")
        self.assertEqual(deposit.available_delta, Decimal("40.00"))
        self.assertEqual(deposit.debt_delta, Decimal("0.00"))
        self.assertEqual(deposit.actor_type, AccountTransactionActorType.MANAGER)
        self.assertEqual(deposit.created_by, self.manager)

        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(Invoice.objects.count(), 0)

    # Проверяем конфликт ключа между заказами одного клиента:
    # ключ первого поступления нельзя использовать для другого заказа,
    # даже при одинаковой сумме и общем финансовом счёте.
    # Отклонённый запрос не создаёт платёж и не меняет баланс.
    def test_receipt_key_cannot_be_reused_for_another_order(self):
        other_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
            payment_method=PaymentMethod.ON_RECEIPT,
        )

        receipt_data = {
            "amount": Decimal("40.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "office:receipt:order-conflict:001",
            "created_by": self.manager,
        }

        first_payment = record_manual_order_payment(
            order=self.order,
            **receipt_data,
        )

        with self.assertRaisesMessage(
                ValidationError,
                "Operation key is already used for different payment data.",
        ):
            record_manual_order_payment(
                order=other_order,
                **receipt_data,
            )

        self.account.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Payment.objects.get().pk, first_payment.pk)
        self.assertFalse(other_order.payments.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.account.available_balance, Decimal("40.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))

    # Проверяем откат регистрации поступления:
    # если после пополнения не удалось создать Payment,
    # финансовая операция и изменение баланса откатываются.
    # Заказ остаётся без изменений.
    def test_payment_creation_failure_rolls_back_deposit_and_balance(self):
        with patch(
                "shop_epower.payments.services.receipts.Payment.objects.create",
                side_effect=RuntimeError("Payment creation failed."),
        ) as mocked_create:
            with self.assertRaisesMessage(
                    RuntimeError,
                    "Payment creation failed.",
            ):
                record_manual_order_payment(
                    order=self.order,
                    amount=Decimal("40.00"),
                    method=PaymentMethod.ON_RECEIPT,
                    operation_key="office:receipt:rollback:001",
                    created_by=self.manager,
                )

            mocked_create.assert_called_once()

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(self.account.transactions.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.order.total_price, Decimal("100.00"))

    # Проверяем защиту самостоятельного пополнения:
    # если ключ уже принадлежит операции без связанного Payment,
    # регистрация платежа отклоняется.
    # Существующее пополнение и баланс сохраняются без изменений.
    def test_receipt_cannot_adopt_deposit_without_payment(self):
        operation_key = "office:receipt:unlinked:001"
        comment = "Standalone deposit."

        deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("40.00"),
            operation_key=operation_key,
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
            comment=comment,
        )

        with self.assertRaisesMessage(
                ValidationError,
                "Operation key is already used for different payment data.",
        ):
            record_manual_order_payment(
                order=self.order,
                amount=Decimal("40.00"),
                method=PaymentMethod.ON_RECEIPT,
                operation_key=operation_key,
                created_by=self.manager,
                comment=comment,
            )

        self.account.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.account.transactions.get().pk, deposit.pk)
        self.assertEqual(self.account.available_balance, Decimal("40.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))

    # Проверяем запрет самостоятельного подтверждения оплаты клиентом:
    # пользователь с ролью CLIENT не может зарегистрировать поступление.
    # Платёж, финансовая операция и изменение баланса не создаются.
    def test_customer_cannot_record_manual_payment(self):
        with self.assertRaisesMessage(
                ValidationError,
                "Only managers and administrators can record payments.",
        ):
            record_manual_order_payment(
                order=self.order,
                amount=Decimal("40.00"),
                method=PaymentMethod.ON_RECEIPT,
                operation_key="office:receipt:customer-forbidden:001",
                created_by=self.user,
            )

        self.account.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(self.account.transactions.count(), 0)
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))

    # Проверяем регистрацию поступления администратором:
    # платёж создаётся в PAID, деньги поступают на счёт клиента,
    # а журнал сохраняет администратора и его роль на момент операции.
    def test_admin_can_record_manual_payment(self):
        admin = create_test_admin()

        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("40.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="office:receipt:admin:001",
            created_by=admin,
        )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        deposit = payment.deposit_transaction

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.amount, Decimal("40.00"))
        self.assertEqual(deposit.account, self.account)
        self.assertEqual(deposit.created_by, admin)
        self.assertEqual(deposit.actor_type, AccountTransactionActorType.ADMIN)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.account.available_balance, Decimal("40.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))

    # Проверяем защиту подтверждённого поступления:
    # старый сброс в PENDING запрещён для платежа с пополнением.
    # Статус, связь, комментарий, история и баланс остаются прежними.
    def test_linked_receipt_cannot_be_reset_to_pending(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("40.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="office:receipt:reset-forbidden:001",
            created_by=self.manager,
            comment="Office receipt confirmed.",
        )

        deposit_id = payment.deposit_transaction_id
        history_count = payment.history.count()
        admin = create_test_admin()

        with self.assertRaisesMessage(
                ValidationError,
                "A payment linked to a financial deposit cannot be reset to pending.",
        ):
            reset_payment_to_pending(
                payment=payment,
                comment="Reset attempted.",
                changed_by=admin,
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.deposit_transaction_id, deposit_id)
        self.assertEqual(payment.manager_comment, "Office receipt confirmed.")
        self.assertEqual(payment.history.count(), history_count)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.account.available_balance, Decimal("40.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))

    # Проверяем повтор регистрации одного поступления:
    # одинаковые данные и ключ возвращают существующий платёж.
    # Второй платёж и повторное пополнение не создаются.
    def test_repeated_receipt_returns_same_payment_without_double_credit(self):
        receipt_data = {
            "order": self.order,
            "amount": Decimal("40.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "office:receipt:idempotent:001",
            "created_by": self.manager,
            "comment": "Payment received in the office.",
        }

        first_payment = record_manual_order_payment(
            **receipt_data,
        )
        repeated_payment = record_manual_order_payment(
            **receipt_data,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            repeated_payment.pk,
            first_payment.pk,
        )
        self.assertEqual(
            repeated_payment.deposit_transaction_id,
            first_payment.deposit_transaction_id,
        )
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем несколько поступлений по одному заказу:
    # офисная и безналичная оплаты создают отдельные платежи
    # и отдельные пополнения доступного баланса.
    # Деньги автоматически не распределяются, долг не возникает.
    def test_office_and_bank_receipts_credit_same_order_account(self):
        office_payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("40.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:office:partial:001",
            created_by=self.manager,
        )

        bank_payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("60.00"),
            method=PaymentMethod.INVOICE,
            operation_key="receipt:bank:partial:001",
            created_by=self.manager,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertNotEqual(office_payment.pk, bank_payment.pk)
        self.assertNotEqual(
            office_payment.deposit_transaction_id,
            bank_payment.deposit_transaction_id,
        )

        self.assertEqual(self.order.payments.count(), 2)
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(office_payment.amount, Decimal("40.00"))
        self.assertEqual(bank_payment.amount, Decimal("60.00"))
        self.assertEqual(office_payment.method, PaymentMethod.ON_RECEIPT)
        self.assertEqual(bank_payment.method, PaymentMethod.INVOICE)

        for payment in (office_payment, bank_payment):
            self.assertEqual(payment.status, PaymentStatus.PAID)
            self.assertEqual(payment.provider, PaymentProvider.MANUAL)
            self.assertEqual(
                payment.deposit_transaction.operation_type,
                AccountTransactionType.DEPOSIT,
            )

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertFalse(
            Invoice.objects.filter(order=self.order).exists(),
        )