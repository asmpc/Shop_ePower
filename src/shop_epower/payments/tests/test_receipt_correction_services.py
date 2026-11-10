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
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.services import (
    assign_order_funds,
    cancel_order_fund_assignment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import PaymentMethod, PaymentStatus
from shop_epower.payments.services import (
    cancel_manual_order_payment,
    record_manual_order_payment,
)


class TestsPaymentReceiptCorrectionServices(TestCase):
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

    # Проверяем отмену ошибочного поступления без назначений:
    # платёж становится CANCELLED, пополнение сторнируется,
    # доступный баланс возвращается к нулю, долг не меняется.
    # Исходная финансовая операция сохраняется вместе со сторно.
    def test_manager_can_cancel_unassigned_receipt(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:correction:original",
            created_by=self.manager,
        )
        deposit = payment.deposit_transaction

        cancel_manual_order_payment(
            payment=payment,
            operation_key="receipt:correction:cancel",
            created_by=self.manager,
            comment="Receipt registered by mistake.",
        )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(payment.deposit_transaction_id, deposit.pk)
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 2)

        reversal = self.account.transactions.get(reversal_of=deposit)

        self.assertEqual(
            reversal.operation_type,
            AccountTransactionType.REVERSAL,
        )
        self.assertEqual(reversal.available_delta, Decimal("-100.00"))
        self.assertEqual(reversal.debt_delta, Decimal("0.00"))

    # Проверяем историю отмены поступления:
    # сохраняются переход PAID → CANCELLED,
    # обязательная причина и сотрудник, выполнивший отмену.
    def test_cancellation_records_payment_history(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:history:original",
            created_by=self.manager,
        )
        reason = "Money was not actually received."

        cancel_manual_order_payment(
            payment=payment,
            operation_key="receipt:history:cancel",
            created_by=self.manager,
            comment=reason,
        )

        self.assertEqual(payment.history.count(), 1)

        history = payment.history.get()

        self.assertEqual(history.old_status, PaymentStatus.PAID)
        self.assertEqual(history.new_status, PaymentStatus.CANCELLED)
        self.assertEqual(history.comment, reason)
        self.assertEqual(history.changed_by, self.manager)

    # Проверяем обязательную причину отмены:
    # пустая строка и пробелы отклоняются.
    # Платёж остаётся PAID, баланс и история не меняются.
    def test_cancellation_requires_nonblank_reason(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:required-reason:original",
            created_by=self.manager,
        )

        for reason in ("", "   "):
            with self.subTest(reason=reason):
                with self.assertRaises(ValidationError):
                    cancel_manual_order_payment(
                        payment=payment,
                        operation_key="receipt:required-reason:cancel",
                        created_by=self.manager,
                        comment=reason,
                    )

                payment.refresh_from_db()
                self.account.refresh_from_db()

                self.assertEqual(payment.status, PaymentStatus.PAID)
                self.assertEqual(
                    self.account.available_balance,
                    Decimal("100.00"),
                )
                self.assertEqual(
                    self.account.debt_balance,
                    Decimal("0.00"),
                )
                self.assertEqual(self.account.transactions.count(), 1)
                self.assertEqual(payment.history.count(), 0)

    # Проверяем защиту поступления с действующим назначением:
    # его нельзя отменить, даже если других денег на счёте достаточно.
    # Сначала сотрудник должен отдельно снять зависимое назначение.
    # Отклонённая отмена сохраняет платёж, баланс и историю.
    def test_cannot_cancel_receipt_with_active_assignment(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:dependent:first",
            created_by=self.manager,
        )

        assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="receipt:dependent:assignment",
            created_by=self.manager,
        )

        record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:dependent:extra",
            created_by=self.manager,
        )

        with self.assertRaises(ValidationError):
            cancel_manual_order_payment(
                payment=payment,
                operation_key="receipt:dependent:cancel",
                created_by=self.manager,
                comment="Receipt registered by mistake.",
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("140.00"),
        )
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(payment.history.count(), 0)

    # Проверяем отмену поступления после снятия назначения:
    # освобождённые деньги можно сторнировать.
    # Историческая связь назначения с поступлением сохраняется,
    # но уже не блокирует отмену.
    def test_can_cancel_receipt_after_assignment_cancellation(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:released:original",
            created_by=self.manager,
        )

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="receipt:released:assignment",
            created_by=self.manager,
        )

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="receipt:released:assignment-cancel",
            created_by=self.manager,
            comment="Release funds to correct the receipt.",
        )

        cancel_manual_order_payment(
            payment=payment,
            operation_key="receipt:released:cancel",
            created_by=self.manager,
            comment="Receipt registered by mistake.",
        )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 4)
        self.assertEqual(payment.history.count(), 1)

        self.assertEqual(
            assignment.sources.get().deposit_transaction_id,
            payment.deposit_transaction_id,
        )

    # Проверяем повтор отмены с тем же ключом и данными:
    # сервис возвращает тот же платёж,
    # не создаёт второе сторно и не дублирует историю.
    def test_same_cancellation_key_is_idempotent(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:retry:original",
            created_by=self.manager,
        )

        cancellation_data = {
            "payment": payment,
            "operation_key": "receipt:retry:cancel",
            "created_by": self.manager,
            "comment": "Receipt registered by mistake.",
        }

        first_result = cancel_manual_order_payment(**cancellation_data)
        repeated_result = cancel_manual_order_payment(**cancellation_data)

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(first_result.pk, payment.pk)
        self.assertEqual(repeated_result.pk, payment.pk)
        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(payment.history.count(), 1)

    # Проверяем конфликт причины при повторе отмены:
    # тот же ключ с другим комментарием отклоняется.
    # Первоначальная причина в обеих историях сохраняется.
    def test_cancellation_retry_rejects_changed_reason(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:reason-conflict:original",
            created_by=self.manager,
        )
        original_reason = "Money was not actually received."

        cancellation_data = {
            "payment": payment,
            "operation_key": "receipt:reason-conflict:cancel",
            "created_by": self.manager,
            "comment": original_reason,
        }

        cancel_manual_order_payment(**cancellation_data)

        cancellation_data["comment"] = "A different cancellation reason."

        with self.assertRaises(ValidationError):
            cancel_manual_order_payment(**cancellation_data)

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(payment.history.count(), 1)
        self.assertEqual(payment.history.get().comment, original_reason)

        reversal = self.account.transactions.get(
            reversal_of=payment.deposit_transaction,
        )
        self.assertEqual(reversal.comment, original_reason)

    # Проверяем повторную отмену с новым ключом:
    # уже отменённое поступление нельзя списать повторно.
    # Другие доступные деньги и первоначальная история сохраняются.
    def test_cannot_cancel_receipt_again_with_another_key(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:another-key:original",
            created_by=self.manager,
        )
        first_key = "receipt:another-key:first-cancel"

        cancellation_data = {
            "payment": payment,
            "operation_key": first_key,
            "created_by": self.manager,
            "comment": "Receipt registered by mistake.",
        }

        cancel_manual_order_payment(**cancellation_data)

        record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:another-key:extra",
            created_by=self.manager,
        )

        cancellation_data["operation_key"] = "receipt:another-key:second-cancel"

        with self.assertRaises(ValidationError):
            cancel_manual_order_payment(**cancellation_data)

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.account.available_balance, Decimal("100.00"))
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(payment.history.count(), 1)

        reversal = self.account.transactions.get(
            reversal_of=payment.deposit_transaction,
        )
        self.assertEqual(reversal.operation_key, first_key)

    # Проверяем запрет отмены поступления клиентом:
    # даже владелец счёта не может выполнить служебное исправление.
    # Платёж, баланс и история остаются без изменений.
    def test_customer_cannot_cancel_receipt(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:customer-denied:original",
            created_by=self.manager,
        )

        with self.assertRaises(ValidationError):
            cancel_manual_order_payment(
                payment=payment,
                operation_key="receipt:customer-denied:cancel",
                created_by=self.user,
                comment="Cancel my receipt.",
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(self.account.available_balance, Decimal("100.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(payment.history.count(), 0)

    # Проверяем отмену безналичного поступления администратором:
    # поступление зарегистрировал менеджер,
    # а автором сторно и изменения статуса становится администратор.
    def test_admin_can_cancel_bank_receipt(self):
        admin = create_test_admin()

        self.order.payment_method = PaymentMethod.INVOICE
        self.order.save(update_fields=["payment_method"])

        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.INVOICE,
            operation_key="receipt:admin-bank:original",
            created_by=self.manager,
        )

        cancel_manual_order_payment(
            payment=payment,
            operation_key="receipt:admin-bank:cancel",
            created_by=admin,
            comment="Bank receipt registered by mistake.",
        )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 2)

        history = payment.history.get()
        self.assertEqual(history.changed_by, admin)

        reversal = self.account.transactions.get(
            reversal_of=payment.deposit_transaction,
        )
        self.assertEqual(
            reversal.actor_type,
            AccountTransactionActorType.ADMIN,
        )
        self.assertEqual(reversal.created_by, admin)

    # Проверяем запрет исправления для неактивного менеджера:
    # сохранённая роль не даёт права отменять поступление
    # после блокировки учётной записи.
    def test_inactive_manager_cannot_cancel_receipt(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:inactive-manager:original",
            created_by=self.manager,
        )

        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            cancel_manual_order_payment(
                payment=payment,
                operation_key="receipt:inactive-manager:cancel",
                created_by=self.manager,
                comment="Receipt registered by mistake.",
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(self.account.available_balance, Decimal("100.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(payment.history.count(), 0)

    # Проверяем атомарность отмены поступления:
    # ошибка создания истории откатывает сторно,
    # изменение баланса и статус платежа.
    def test_history_creation_failure_rolls_back_cancellation(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:cancel-rollback:original",
            created_by=self.manager,
        )

        with patch(
            "shop_epower.payments.services.receipts.PaymentHistory.objects.create",
            side_effect=RuntimeError("Payment history creation failed."),
        ) as mocked_create:
            with self.assertRaisesMessage(
                RuntimeError,
                "Payment history creation failed.",
            ):
                cancel_manual_order_payment(
                    payment=payment,
                    operation_key="receipt:cancel-rollback:cancel",
                    created_by=self.manager,
                    comment="Receipt registered by mistake.",
                )

            mocked_create.assert_called_once()

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(self.account.available_balance, Decimal("100.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(payment.history.count(), 0)
