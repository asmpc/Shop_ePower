from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.models import (
    AccountTransactionActorType,
    AccountTransactionType,
)
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_deposit,
)
from shop_epower.orders.models import OrderItem, OrderStatus
from shop_epower.orders.services import (
    assign_order_funds,
    cancel_order_fund_assignment,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import PaymentMethod, PaymentStatus
from shop_epower.payments.services import (
    cancel_manual_order_payment,
    record_manual_account_payment,
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

    def _ship_order(self):
        """Готовит товарную позицию и полностью отгружает заказ."""
        product = create_test_product(
            base_price=self.order.total_price,
        )

        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            unit_price=self.order.total_price,
            quantity=1,
            total_price=self.order.total_price,
            currency_snapshot=self.order.currency_snapshot,
        )

        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        return complete_order_shipment(
            order=self.order,
            created_by=self.manager,
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

    # Несовпадение суммы платежа и пополнения запрещает отмену.
    # Баланс, статус платежа и история остаются без изменений.
    def test_cannot_cancel_receipt_with_mismatched_amount(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:amount-mismatch:original",
            created_by=self.manager,
        )

        payment.amount = Decimal("90.00")
        payment.save(update_fields=["amount"])

        with self.assertRaisesMessage(
            ValidationError,
            "Payment amount does not match its deposit.",
        ):
            cancel_manual_order_payment(
                payment=payment,
                operation_key="receipt:amount-mismatch:cancel",
                created_by=self.manager,
                comment="Receipt registered by mistake.",
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.amount, Decimal("90.00"))
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

    # Разные валюты платежа и пополнения запрещают отмену.
    # Статус, баланс и история остаются без изменений.
    def test_cannot_cancel_receipt_with_mismatched_currency(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:currency-mismatch:original",
            created_by=self.manager,
        )

        different_currency = (
            "USD" if payment.currency_snapshot != "USD" else "EUR"
        )
        payment.currency_snapshot = different_currency
        payment.save(update_fields=["currency_snapshot"])

        with self.assertRaisesMessage(
            ValidationError,
            "Payment currency does not match its deposit.",
        ):
            cancel_manual_order_payment(
                payment=payment,
                operation_key="receipt:currency-mismatch:cancel",
                created_by=self.manager,
                comment="Receipt registered by mistake.",
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(
            payment.currency_snapshot,
            different_currency,
        )
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

    # Платёж заказа нельзя отменить через пополнение другого счёта.
    # Оба баланса, статус платежа и история сохраняются.
    def test_cannot_cancel_receipt_with_another_account_deposit(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:account-mismatch:original",
            created_by=self.manager,
        )

        other_user = create_test_user()
        other_account = create_personal_customer_account(
            user=other_user,
        )
        other_deposit = record_customer_deposit(
            account=other_account,
            amount=Decimal("100.00"),
            operation_key="receipt:account-mismatch:other-deposit",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )

        payment.deposit_transaction = other_deposit
        payment.save(update_fields=["deposit_transaction"])

        with self.assertRaisesMessage(
            ValidationError,
            "Payment order account does not match its deposit account.",
        ):
            cancel_manual_order_payment(
                payment=payment,
                operation_key="receipt:account-mismatch:cancel",
                created_by=self.manager,
                comment="Receipt registered by mistake.",
            )

        payment.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.history.count(), 0)

        for account in (self.account, other_account):
            with self.subTest(account_id=account.pk):
                account.refresh_from_db()

                self.assertEqual(
                    account.available_balance,
                    Decimal("100.00"),
                )
                self.assertEqual(
                    account.debt_balance,
                    Decimal("0.00"),
                )
                self.assertEqual(account.transactions.count(), 1)

    # Поступление без заказа можно отменить, пока деньги не назначены.
    # Платёж сохраняется со статусом CANCELLED, пополнение сторнируется.
    def test_manager_can_cancel_unassigned_account_receipt(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:account-correction:original",
            created_by=self.manager,
        )
        deposit = payment.deposit_transaction

        self.assertIsNone(payment.order_id)

        cancel_manual_order_payment(
            payment=payment,
            operation_key="receipt:account-correction:cancel",
            created_by=self.manager,
            comment="Receipt registered by mistake.",
        )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(payment.deposit_transaction_id, deposit.pk)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertTrue(
            self.account.transactions.filter(
                reversal_of_id=deposit.pk,
            ).exists(),
        )
        self.assertEqual(payment.history.count(), 1)

    # Отмена неназначенного поступления после отгрузки
    # убирает доступные деньги, сохраняя долг и завершённую отгрузку.
    def test_cancelling_receipt_after_shipment_preserves_debt(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:after-shipment:original",
            created_by=self.manager,
        )

        shipment = self._ship_order()

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )

        cancel_manual_order_payment(
            payment=payment,
            operation_key="receipt:after-shipment:cancel",
            created_by=self.manager,
            comment="Money was not actually received.",
        )

        payment.refresh_from_db()
        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.shipments.get(), shipment)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)

    # Использованное поступление без заказа сначала освобождается
    # снятием назначения. Последующая отмена сохраняет долг и отгрузку.
    def test_account_receipt_cancellation_after_shipment_requires_release(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:postship-dependent:original",
            created_by=self.manager,
        )

        self._ship_order()

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="receipt:postship-dependent:assignment",
            created_by=self.manager,
        )
        reason = "Receipt registered by mistake."

        with self.assertRaisesMessage(
            ValidationError,
            "Cancel dependent fund assignments before cancelling the receipt.",
        ):
            cancel_manual_order_payment(
                payment=payment,
                operation_key="receipt:postship-dependent:cancel",
                created_by=self.manager,
                comment=reason,
            )

        payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.history.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="receipt:postship-dependent:release",
            created_by=self.manager,
            comment="Release funds before correcting the receipt.",
        )

        cancel_manual_order_payment(
            payment=payment,
            operation_key="receipt:postship-dependent:cancel",
            created_by=self.manager,
            comment=reason,
        )

        payment.refresh_from_db()
        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(payment.history.count(), 1)
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
