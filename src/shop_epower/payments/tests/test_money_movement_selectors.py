from decimal import Decimal

from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PayoutMethod,
)
from shop_epower.payments.selectors import get_money_movements_for_staff
from shop_epower.payments.services import (
    cancel_manual_order_payment,
    create_payment_for_order,
    mark_payment_paid,
    record_manual_account_payment,
    record_manual_account_payout,
    record_manual_order_payment,
)


class TestsStaffMoneyMovementSelectors(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )

        self.receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="money-movement:receipt",
            created_by=self.manager,
            comment="Money received in the office.",
        )

        self.payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="money-movement:payout",
            created_by=self.manager,
            comment="Money returned to the customer.",
        )

    # Проверяем общую выборку денежных движений счёта:
    # поступление и выплата представлены отдельными строками
    # с видом операции, суммой и username автора.
    def test_account_movements_include_receipt_and_payout(self):
        movements = get_money_movements_for_staff(
            account_id=self.account.pk,
        )

        self.assertCountEqual(
            [
                (
                    movement["kind"],
                    movement["entry_id"],
                    movement["amount"],
                    movement["performed_by"],
                )
                for movement in movements
            ],
            [
                (
                    "receipt",
                    self.receipt.pk,
                    Decimal("100.00"),
                    self.manager.username,
                ),
                (
                    "payout",
                    self.payout.pk,
                    Decimal("40.00"),
                    self.manager.username,
                ),
            ],
        )

    # Проверяем общую хронологию денежных движений:
    # поступления и выплаты сортируются вместе от новых к старым.
    def test_movements_are_sorted_newest_first(self):
        newest_receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("20.00"),
            method=PaymentMethod.INVOICE,
            operation_key="money-movement:newest-receipt",
            created_by=self.manager,
            comment="Additional bank transfer received.",
        )

        movements = get_money_movements_for_staff(
            account_id=self.account.pk,
        )

        self.assertEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("receipt", newest_receipt.pk),
                ("payout", self.payout.pk),
                ("receipt", self.receipt.pk),
            ],
        )

    # Проверяем отсутствие загрузки истории без условий:
    # результат пустой, запросы к базе данных не выполняются.
    def test_no_search_conditions_returns_no_movements(self):
        with self.assertNumQueries(0):
            movements = get_money_movements_for_staff()

            self.assertEqual(list(movements), [])

    # Проверяем изоляцию счетов в общем списке:
    # поступления и выплаты одного клиента не попадают
    # в результат поиска по счёту другого клиента.
    def test_account_filter_excludes_other_account_movements(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(
            user=other_user,
        )

        movements = get_money_movements_for_staff(
            account_id=other_account.pk,
        )

        self.assertEqual(list(movements), [])

    # Проверяем поиск по Returned без ограничения по счёту:
    # отображаются выплаты разных клиентов,
    # поступления в результат не попадают.
    def test_payout_filter_without_account_includes_multiple_accounts(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(
            user=other_user,
        )

        record_manual_account_payment(
            account=other_account,
            amount=Decimal("30.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="money-movement:other-account:receipt",
            created_by=self.manager,
            comment="Money received from another customer.",
        )

        other_payout = record_manual_account_payout(
            account=other_account,
            amount=Decimal("10.00"),
            method=PayoutMethod.CASH,
            operation_key="money-movement:other-account:payout",
            created_by=self.manager,
            comment="Money returned to another customer.",
        )

        movements = get_money_movements_for_staff(
            status="returned",
        )

        self.assertCountEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("payout", self.payout.pk),
                ("payout", other_payout.pk),
            ],
        )

    # Проверяем общие данные для карточек денежных движений:
    # поступление и выплата содержат счёт, клиента,
    # валюту и свой фактический способ операции.
    def test_movements_include_account_customer_currency_and_method(self):
        movements = get_money_movements_for_staff(
            account_id=self.account.pk,
        )

        self.assertCountEqual(
            [
                (
                    movement["kind"],
                    movement["account_id"],
                    movement["customer_email"],
                    movement["currency"],
                    movement["method"],
                )
                for movement in movements
            ],
            [
                (
                    "receipt",
                    self.account.pk,
                    self.user.email,
                    self.account.currency,
                    PaymentMethod.ON_RECEIPT,
                ),
                (
                    "payout",
                    self.account.pk,
                    self.user.email,
                    self.account.currency,
                    PayoutMethod.CASH,
                ),
            ],
        )

    # Проверяем поиск денежных движений по email клиента:
    # регистр букв не влияет на поиск;
    # для отсутствующего email результат пустой.
    def test_customer_email_filters_receipts_and_payouts(self):
        movements = get_money_movements_for_staff(
            customer_email=self.user.email.upper(),
        )

        self.assertCountEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("receipt", self.receipt.pk),
                ("payout", self.payout.pk),
            ],
        )

        missing_movements = get_money_movements_for_staff(
            customer_email="missing@example.test",
        )

        self.assertEqual(list(missing_movements), [])

    # Проверяем статусы общего журнала:
    # подтверждённое поступление отображается как Paid,
    # выполненная выплата — как Returned.
    def test_movements_show_paid_receipt_and_returned_payout(self):
        movements = get_money_movements_for_staff(
            account_id=self.account.pk,
        )

        self.assertCountEqual(
            [
                (movement["kind"], movement["status"])
                for movement in movements
            ],
            [
                ("receipt", "paid"),
                ("payout", "returned"),
            ],
        )

    # Проверяем исключение ожидающей попытки оплаты:
    # Pending сохраняется в прежнем платёжном сценарии,
    # но не показывается в журнале денежных движений.
    def test_pending_payment_attempt_is_excluded_from_journal(self):
        order = create_test_order(
            user=self.user,
            customer_account=self.account,
        )

        pending_payment = create_payment_for_order(
            order=order,
            method=PaymentMethod.ONLINE,
        )

        movements = get_money_movements_for_staff(
            account_id=self.account.pk,
        )

        self.assertCountEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("receipt", self.receipt.pk),
                ("payout", self.payout.pk),
            ],
        )

        pending_payment.refresh_from_db()

        self.assertEqual(
            pending_payment.status,
            PaymentStatus.PENDING,
        )

    # Проверяем поиск по статусу Returned:
    # отображаются выполненные возвраты,
    # подтверждённые поступления исключаются.
    def test_status_filter_returns_only_returned_movements(self):
        movements = get_money_movements_for_staff(
            status="returned",
        )

        self.assertEqual(
            [
                (
                    movement["kind"],
                    movement["entry_id"],
                    movement["status"],
                )
                for movement in movements
            ],
            [
                ("payout", self.payout.pk, "returned"),
            ],
        )

    # Проверяем поиск по статусу Paid:
    # отображается подтверждённое поступление,
    # выполненный возврат в результат не попадает.
    def test_status_filter_returns_only_paid_receipts(self):
        movements = get_money_movements_for_staff(
            status=PaymentStatus.PAID,
        )

        self.assertEqual(
            [
                (
                    movement["kind"],
                    movement["entry_id"],
                    movement["status"],
                )
                for movement in movements
            ],
            [
                ("receipt", self.receipt.pk, PaymentStatus.PAID),
            ],
        )

    # Проверяем поиск по статусу Cancelled:
    # отменённое поступление остаётся видимым в истории,
    # действующие поступления и выплаты исключаются.
    def test_status_filter_returns_only_cancelled_receipts(self):
        receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("30.00"),
            method=PaymentMethod.INVOICE,
            operation_key="money-movement:receipt-to-cancel",
            created_by=self.manager,
            comment="Bank receipt registered.",
        )

        cancel_manual_order_payment(
            payment=receipt,
            operation_key="money-movement:cancel-receipt",
            created_by=self.manager,
            comment="Receipt registered by mistake.",
        )

        movements = get_money_movements_for_staff(
            status=PaymentStatus.CANCELLED,
        )

        self.assertEqual(
            [
                (
                    movement["kind"],
                    movement["entry_id"],
                    movement["status"],
                )
                for movement in movements
            ],
            [
                ("receipt", receipt.pk, PaymentStatus.CANCELLED),
            ],
        )

    # Проверяем общий фильтр банковского перевода:
    # он находит безналичное поступление и банковский возврат,
    # исключая операции наличными из общей подготовки.
    def test_bank_method_filter_includes_receipts_and_payouts(self):
        bank_receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("30.00"),
            method=PaymentMethod.INVOICE,
            operation_key="money-movement:bank-receipt",
            created_by=self.manager,
            comment="Bank transfer received.",
        )

        bank_payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("20.00"),
            method=PayoutMethod.BANK_TRANSFER,
            operation_key="money-movement:bank-payout",
            created_by=self.manager,
            comment="Bank transfer returned to the customer.",
        )

        movements = get_money_movements_for_staff(
            method=PaymentMethod.INVOICE,
        )

        self.assertCountEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("receipt", bank_receipt.pk),
                ("payout", bank_payout.pk),
            ],
        )

    # Проверяем общий фильтр офиса/наличных:
    # отображаются поступление в офисе и возврат наличными,
    # банковское поступление исключается.
    def test_office_method_filter_includes_receipt_and_cash_payout(self):
        record_manual_account_payment(
            account=self.account,
            amount=Decimal("30.00"),
            method=PaymentMethod.INVOICE,
            operation_key="money-movement:bank-receipt-for-office-filter",
            created_by=self.manager,
            comment="Bank transfer received.",
        )

        movements = get_money_movements_for_staff(
            method=PaymentMethod.ON_RECEIPT,
        )

        self.assertCountEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("receipt", self.receipt.pk),
                ("payout", self.payout.pk),
            ],
        )

    # Проверяем фильтр ручных операций:
    # ручное поступление и выплата отображаются,
    # подтверждённая mock-оплата исключается.
    def test_manual_provider_filter_includes_receipt_and_payout(self):
        order = create_test_order(
            user=self.user,
            customer_account=self.account,
        )

        mock_payment = create_payment_for_order(
            order=order,
            method=PaymentMethod.ONLINE,
        )

        mark_payment_paid(
            payment=mock_payment,
            manager_comment="Mock provider payment confirmed.",
            changed_by=self.manager,
        )

        movements = get_money_movements_for_staff(
            provider=PaymentProvider.MANUAL,
        )

        self.assertCountEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("receipt", self.receipt.pk),
                ("payout", self.payout.pk),
            ],
        )

        mock_movements = get_money_movements_for_staff(
            provider=PaymentProvider.MOCK,
        )

        self.assertEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in mock_movements
            ],
            [
                ("receipt", mock_payment.pk),
            ],
        )

    # Проверяем поиск по номеру заказа:
    # отображается связанное с ним поступление;
    # поступления без этого заказа и выплаты счёта исключаются.
    def test_order_filter_returns_only_related_receipts(self):
        order = create_test_order(
            user=self.user,
            customer_account=self.account,
        )

        order_receipt = record_manual_order_payment(
            order=order,
            amount=Decimal("30.00"),
            method=PaymentMethod.INVOICE,
            operation_key="money-movement:order-receipt",
            created_by=self.manager,
            comment="Bank receipt recorded from the order.",
        )

        movements = get_money_movements_for_staff(
            order_id=order.pk,
        )

        self.assertEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("receipt", order_receipt.pk),
            ],
        )

    # Проверяем поиск поступления по идентификатору:
    # возвращается только запись с указанным transaction_id.
    def test_transaction_filter_returns_matching_receipt(self):
        movements = get_money_movements_for_staff(
            transaction_id=self.receipt.transaction_id,
        )

        self.assertEqual(
            [
                (movement["kind"], movement["entry_id"])
                for movement in movements
            ],
            [
                ("receipt", self.receipt.pk),
            ],
        )

    # Проверяем поиск возврата по ключу расходной операции:
    # возвращается только соответствующая выплата,
    # ключ также доступен в данных строки журнала.
    def test_transaction_filter_returns_matching_payout(self):
        operation_key = self.payout.account_transaction.operation_key

        movements = get_money_movements_for_staff(
            transaction_id=operation_key,
        )

        self.assertEqual(
            [
                (
                    movement["kind"],
                    movement["entry_id"],
                    movement["transaction_id"],
                )
                for movement in movements
            ],
            [
                ("payout", self.payout.pk, operation_key),
            ],
        )
