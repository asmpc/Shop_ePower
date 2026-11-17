from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import (
    AccountTransactionActorType,
    AccountTransactionType,
)
from shop_epower.finance.services import (
    create_legal_customer_account,
    create_personal_customer_account,
    record_customer_deposit,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import (
    cancel_manual_order_payment,
    create_invoice_for_payment,
    record_manual_account_payment,
    record_manual_order_payment,
)


class TestsAccountReceiptServices(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

    # Менеджер принимает деньги клиента, у которого нет заказов.
    # Создаются один оплаченный Payment и одно пополнение счёта.
    # Свободный баланс увеличивается, долг остаётся нулевым.
    # Заказ и Invoice автоматически не создаются.
    def test_manager_records_office_receipt_without_order(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:office:receipt:001",
            created_by=self.manager,
            comment="Advance received in the office.",
        )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 1)
        self.assertIsNone(payment.order_id)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.amount, Decimal("100.00"))
        self.assertEqual(payment.method, PaymentMethod.ON_RECEIPT)
        self.assertEqual(payment.provider, PaymentProvider.MANUAL)
        self.assertEqual(payment.currency_snapshot, self.account.currency)

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        self.assertEqual(self.account.transactions.count(), 1)
        deposit = self.account.transactions.get()

        self.assertEqual(payment.deposit_transaction_id, deposit.pk)
        self.assertEqual(deposit.operation_type, AccountTransactionType.DEPOSIT)
        self.assertEqual(deposit.operation_key, "account:office:receipt:001")
        self.assertEqual(deposit.actor_type, AccountTransactionActorType.MANAGER)
        self.assertEqual(deposit.created_by, self.manager)

        self.assertFalse(self.user.orders.exists())
        self.assertFalse(Invoice.objects.exists())

    # Повтор регистрации с тем же ключом и данными возвращает
    # существующий Payment без второго поступления и зачисления.
    def test_repeated_receipt_returns_existing_payment(self):
        receipt_data = {
            "account": self.account,
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "account:office:receipt:repeat",
            "created_by": self.manager,
            "comment": "Advance received in the office.",
        }

        first_payment = record_manual_account_payment(**receipt_data)
        repeated_payment = record_manual_account_payment(**receipt_data)

        self.account.refresh_from_db()

        self.assertEqual(repeated_payment.pk, first_payment.pk)
        self.assertEqual(
            repeated_payment.deposit_transaction_id,
            first_payment.deposit_transaction_id,
        )
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Ключ поступления нельзя повторно использовать с другим способом оплаты.
    # Ошибка сохраняет исходный платёж, финансовую операцию и баланс.
    def test_receipt_key_cannot_be_reused_for_different_method(self):
        receipt_data = {
            "account": self.account,
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "account:receipt:method-conflict",
            "created_by": self.manager,
            "comment": "Advance received.",
        }

        first_payment = record_manual_account_payment(**receipt_data)

        receipt_data["method"] = PaymentMethod.INVOICE

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for different payment data.",
        ):
            record_manual_account_payment(**receipt_data)

        first_payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(first_payment.method, PaymentMethod.ON_RECEIPT)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Если Payment не удалось сохранить после пополнения,
    # финансовая операция и увеличение баланса откатываются.
    def test_payment_creation_failure_rolls_back_deposit_and_balance(self):
        with patch(
            "shop_epower.payments.services.receipts.Payment.objects.create",
            side_effect=RuntimeError("Payment creation failed."),
        ) as mocked_create:
            with self.assertRaisesMessage(
                RuntimeError,
                "Payment creation failed.",
            ):
                record_manual_account_payment(
                    account=self.account,
                    amount=Decimal("100.00"),
                    method=PaymentMethod.ON_RECEIPT,
                    operation_key="account:receipt:rollback",
                    created_by=self.manager,
                )

            mocked_create.assert_called_once()

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Ключ самостоятельного пополнения без Payment нельзя использовать
    # для регистрации поступления. Исходная операция и баланс сохраняются.
    def test_receipt_cannot_adopt_deposit_without_payment(self):
        operation_key = "account:receipt:unlinked"
        comment = "Standalone deposit."

        deposit = record_customer_deposit(
            account=self.account,
            amount=Decimal("100.00"),
            operation_key=operation_key,
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
            comment=comment,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for different payment data.",
        ):
            record_manual_account_payment(
                account=self.account,
                amount=Decimal("100.00"),
                method=PaymentMethod.ON_RECEIPT,
                operation_key=operation_key,
                created_by=self.manager,
                comment=comment,
            )

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.account.transactions.get().pk, deposit.pk)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Ключ поступления через заказ нельзя использовать для поступления
    # без заказа. Исходная связь платежа и баланс сохраняются.
    def test_account_receipt_cannot_reuse_order_receipt_key(self):
        order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
            payment_method=PaymentMethod.ON_RECEIPT,
        )

        receipt_data = {
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "receipt:order-context",
            "created_by": self.manager,
        }

        payment = record_manual_order_payment(
            order=order,
            **receipt_data,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is already used for different payment data.",
        ):
            record_manual_account_payment(
                account=self.account,
                **receipt_data,
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.order_id, order.pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # После отмены поступления его ключ нельзя использовать повторно.
    # Платёж остаётся CANCELLED, пополнение и сторно сохраняются,
    # баланс не увеличивается и новая история не создаётся.
    def test_cancelled_receipt_key_cannot_be_reused(self):
        receipt_data = {
            "account": self.account,
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "account:receipt:cancelled",
            "created_by": self.manager,
        }

        payment = record_manual_account_payment(**receipt_data)

        cancel_manual_order_payment(
            payment=payment,
            operation_key="account:receipt:cancelled:reversal",
            created_by=self.manager,
            comment="Receipt registered by mistake.",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Payment deposit has already been reversed.",
        ):
            record_manual_account_payment(**receipt_data)

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(payment.history.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Безналичное поступление можно принять без заказа и Invoice.
    # Деньги увеличивают свободный баланс, долг не возникает.
    def test_bank_receipt_does_not_require_order_or_invoice(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("60.00"),
            method=PaymentMethod.INVOICE,
            operation_key="account:bank:receipt:001",
            created_by=self.manager,
        )

        self.account.refresh_from_db()

        self.assertEqual(payment.method, PaymentMethod.INVOICE)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertIsNone(payment.order_id)
        self.assertFalse(self.user.orders.exists())
        self.assertFalse(Invoice.objects.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # У клиента есть личный и юридический счета.
    # Поступление зачисляется на выбранный юридический счёт.
    # Балансы и журнал личного счёта не меняются.
    def test_receipt_credits_selected_legal_account_only(self):
        profile = create_test_legal_profile(user=self.user)
        legal_account = create_legal_customer_account(
            legal_profile=profile,
        )

        payment = record_manual_account_payment(
            account=legal_account,
            amount=Decimal("100.00"),
            method=PaymentMethod.INVOICE,
            operation_key="account:legal:receipt:001",
            created_by=self.manager,
        )

        legal_account.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            payment.deposit_transaction.account_id,
            legal_account.pk,
        )
        self.assertEqual(
            legal_account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            legal_account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.account.transactions.exists())

    # Клиент не может самостоятельно подтвердить поступление денег.
    # Отклонённый вызов не создаёт записи и не меняет баланс.
    def test_customer_cannot_record_receipt(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Only managers and administrators can record payments.",
        ):
            record_manual_account_payment(
                account=self.account,
                amount=Decimal("100.00"),
                method=PaymentMethod.ON_RECEIPT,
                operation_key="account:receipt:customer-forbidden",
                created_by=self.user,
            )

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Администратор может зарегистрировать поступление.
    # Финансовая операция сохраняет его роль ADMIN и автора.
    def test_admin_can_record_receipt_with_admin_actor(self):
        admin = create_test_admin()

        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:admin",
            created_by=admin,
        )

        self.account.refresh_from_db()
        deposit = payment.deposit_transaction

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(
            deposit.actor_type,
            AccountTransactionActorType.ADMIN,
        )
        self.assertEqual(deposit.created_by_id, admin.pk)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Отключённый сотрудник не может зарегистрировать поступление.
    # Проверяем менеджера и администратора без денежных изменений.
    def test_inactive_staff_cannot_record_receipt(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])

        inactive_admin = create_test_admin(is_active=False)

        for actor in (self.manager, inactive_admin):
            with self.subTest(role=actor.role):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Only managers and administrators can record payments.",
                ):
                    record_manual_account_payment(
                        account=self.account,
                        amount=Decimal("100.00"),
                        method=PaymentMethod.ON_RECEIPT,
                        operation_key=f"account:receipt:inactive:{actor.pk}",
                        created_by=actor,
                    )

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Ключ длиннее 255 символов отклоняется с понятной ошибкой.
    # Платёж, финансовая операция и изменение баланса не создаются.
    def test_receipt_rejects_too_long_operation_key(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Operation key is too long.",
        ):
            record_manual_account_payment(
                account=self.account,
                amount=Decimal("100.00"),
                method=PaymentMethod.ON_RECEIPT,
                operation_key="x" * 256,
                created_by=self.manager,
            )

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Ключ должен быть непустой строкой.
    # Отсутствие ключа, пробелы и неверный тип не меняют деньги.
    def test_receipt_requires_nonblank_string_operation_key(self):
        for operation_key in (None, "", "   ", 123):
            with self.subTest(operation_key=operation_key):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Operation key is required.",
                ):
                    record_manual_account_payment(
                        account=self.account,
                        amount=Decimal("100.00"),
                        method=PaymentMethod.ON_RECEIPT,
                        operation_key=operation_key,
                        created_by=self.manager,
                    )

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Некорректная сумма отклоняется без денежных изменений.
    # Проверяем знак, точность, специальные значения и тип данных.
    def test_receipt_rejects_invalid_amount(self):
        invalid_amounts = (
            Decimal("0.00"),
            Decimal("-1.00"),
            Decimal("0.001"),
            Decimal("NaN"),
            Decimal("Infinity"),
            "100.00",
            100,
        )

        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                with self.assertRaises(ValidationError):
                    record_manual_account_payment(
                        account=self.account,
                        amount=amount,
                        method=PaymentMethod.ON_RECEIPT,
                        operation_key="account:receipt:invalid-amount",
                        created_by=self.manager,
                    )

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Ключ поступления закреплён за исходным финансовым счётом.
    # Его повторное использование для другого клиента отклоняется.
    # Первоначальные деньги сохраняются, второй счёт не пополняется.
    def test_receipt_key_cannot_be_reused_for_another_account(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(user=other_user)

        receipt_data = {
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "account:receipt:account-conflict",
            "created_by": self.manager,
        }

        payment = record_manual_account_payment(
            account=self.account,
            **receipt_data,
        )

        with self.assertRaises(ValidationError):
            record_manual_account_payment(
                account=other_account,
                **receipt_data,
            )

        self.account.refresh_from_db()
        other_account.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(
            payment.deposit_transaction.account_id,
            self.account.pk,
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(other_account.transactions.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            other_account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            other_account.debt_balance,
            Decimal("0.00"),
        )

    # Валюта счёта должна совпадать с базовой валютой магазина.
    # Несовпадение отклоняет поступление без денежных изменений.
    def test_receipt_rejects_account_with_non_base_currency(self):
        self.account.currency = (
            "USD" if self.account.currency != "USD" else "EUR"
        )
        self.account.save(update_fields=["currency"])

        with self.assertRaisesMessage(
            ValidationError,
            "Account currency does not match deployment base currency.",
        ):
            record_manual_account_payment(
                account=self.account,
                amount=Decimal("100.00"),
                method=PaymentMethod.ON_RECEIPT,
                operation_key="account:receipt:currency-mismatch",
                created_by=self.manager,
            )

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Для поступления без заказа нельзя создать Invoice.
    # Отказ сохраняет поступление и свободные деньги клиента.
    def test_invoice_cannot_be_created_for_receipt_without_order(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.INVOICE,
            operation_key="account:receipt:invoice-forbidden",
            created_by=self.manager,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Invoice requires an order.",
        ):
            create_invoice_for_payment(
                payment=payment,
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertFalse(Invoice.objects.exists())
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
