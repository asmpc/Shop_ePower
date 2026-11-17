from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.services import assign_order_funds
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import record_manual_account_payment
from shop_epower.payments.tests.helpers import create_test_payment


class TestsManagerReceiptCorrectionAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

        self.payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:correction-api:original",
            created_by=self.manager,
        )

        self.url = reverse(
            "api-payments:manager-cancel-receipt",
            kwargs={"payment_id": self.payment.pk},
        )
        self.payload = {
            "comment": "Money was not actually received.",
            "operation_key": "receipt:correction-api:cancel",
        }

    # Менеджер отменяет поступление без заказа через API.
    # Пополнение сторнируется, причина и сотрудник сохраняются.
    # Ответ содержит обновлённый платёж и ID финансового счёта.
    def test_manager_can_cancel_receipt_without_order(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.payment.pk)
        self.assertEqual(response.data["status"], PaymentStatus.CANCELLED)
        self.assertIsNone(response.data["order"])
        self.assertEqual(
            response.data["customer_account_id"],
            self.account.pk,
        )

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

        reversal = self.account.transactions.get(
            reversal_of_id=self.payment.deposit_transaction_id,
        )
        self.assertEqual(
            reversal.operation_key,
            self.payload["operation_key"],
        )

        history = self.payment.history.get()

        self.assertEqual(history.old_status, PaymentStatus.PAID)
        self.assertEqual(history.new_status, PaymentStatus.CANCELLED)
        self.assertEqual(history.comment, self.payload["comment"])
        self.assertEqual(history.changed_by_id, self.manager.pk)

    # Пустая причина и пробелы отклоняются API.
    # Ответ содержит ошибку поля comment, деньги и история не меняются.
    def test_cancellation_requires_nonblank_reason(self):
        self.client.force_authenticate(user=self.manager)

        for reason in ("", "   "):
            with self.subTest(reason=reason):
                payload = {
                    **self.payload,
                    "comment": reason,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("comment", response.data)

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.payment.history.count(), 0)

    # Отсутствующий, пустой или слишком длинный ключ отклоняется.
    # Ошибка входных данных не меняет поступление и баланс.
    def test_cancellation_requires_valid_operation_key(self):
        self.client.force_authenticate(user=self.manager)

        for operation_key in (None, "", "   ", "x" * 256):
            with self.subTest(operation_key=operation_key):
                payload = self.payload.copy()

                if operation_key is None:
                    payload.pop("operation_key")
                else:
                    payload["operation_key"] = operation_key

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("operation_key", response.data)

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.payment.history.count(), 0)

    # Клиент не может отменить поступление на собственный счёт.
    # Запрет не меняет платёж, баланс или историю.
    def test_customer_cannot_cancel_own_receipt(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.payment.history.count(), 0)

    # Неавторизованный запрос не может отменить поступление.
    # Финансовые данные остаются без изменений.
    def test_anonymous_user_cannot_cancel_receipt(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 401)

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.payment.history.count(), 0)

    # Администратор отменяет выбранное банковское поступление через API.
    # Другое поступление на том же счёте остаётся действующим.
    def test_admin_can_cancel_selected_bank_receipt(self):
        admin = create_test_admin()

        bank_payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("60.00"),
            method=PaymentMethod.INVOICE,
            operation_key="receipt:correction-api:bank",
            created_by=self.manager,
        )
        cancellation_url = reverse(
            "api-payments:manager-cancel-receipt",
            kwargs={"payment_id": bank_payment.pk},
        )

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            cancellation_url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], bank_payment.pk)
        self.assertEqual(response.data["status"], PaymentStatus.CANCELLED)

        bank_payment.refresh_from_db()
        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(bank_payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(self.payment.history.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)

        history = bank_payment.history.get()

        self.assertEqual(history.comment, self.payload["comment"])
        self.assertEqual(history.changed_by_id, admin.pk)

    # Повтор запроса с тем же ключом возвращает отменённый платёж.
    # Второе сторно и дополнительная история не создаются.
    def test_repeated_request_does_not_reverse_receipt_twice(self):
        self.client.force_authenticate(user=self.manager)

        first_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )
        repeated_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(repeated_response.status_code, 200)
        self.assertEqual(first_response.data["id"], self.payment.pk)
        self.assertEqual(repeated_response.data["id"], self.payment.pk)
        self.assertEqual(
            repeated_response.data["status"],
            PaymentStatus.CANCELLED,
        )

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(self.payment.history.count(), 1)

    # Использованное поступление нельзя отменить через API.
    # Отказ сервиса возвращается как 400 с пояснением.
    def test_active_assignment_prevents_receipt_cancellation(self):
        order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
        )
        assign_order_funds(
            order=order,
            amount=Decimal("60.00"),
            operation_key="receipt:correction-api:assignment",
            created_by=self.manager,
        )

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Cancel dependent fund assignments before cancelling the receipt.",
        )

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(self.payment.history.count(), 0)

    # Несуществующий ID возвращает 404.
    # Имеющееся поступление и финансовые данные не меняются.
    def test_missing_payment_returns_404(self):
        self.client.force_authenticate(user=self.manager)

        missing_url = reverse(
            "api-payments:manager-cancel-receipt",
            kwargs={"payment_id": self.payment.pk + 1},
        )

        response = self.client.post(
            missing_url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 404)

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.payment.history.count(), 0)

    # Старый PAID-платёж без пополнения исключён из API отмены.
    # Ответ 404 не меняет запись или деньги клиента.
    def test_legacy_payment_without_deposit_returns_404(self):
        legacy_order = create_test_order(
            user=self.user,
            customer_account=self.account,
        )
        legacy_payment = create_test_payment(
            order=legacy_order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            provider=PaymentProvider.MANUAL,
            status=PaymentStatus.PAID,
            currency_snapshot=self.account.currency,
        )
        legacy_url = reverse(
            "api-payments:manager-cancel-receipt",
            kwargs={"payment_id": legacy_payment.pk},
        )

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            legacy_url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 404)

        legacy_payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(legacy_payment.status, PaymentStatus.PAID)
        self.assertIsNone(legacy_payment.deposit_transaction_id)
        self.assertEqual(legacy_payment.history.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)

    # Изменённый повтор отмены отклоняется.
    # Исходная причина, сторно и история сохраняются.
    def test_conflicting_cancellation_retry_is_rejected(self):
        self.client.force_authenticate(user=self.manager)

        first_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )
        self.assertEqual(first_response.status_code, 200)

        for changes in (
            {"comment": "Changed cancellation reason."},
            {"operation_key": "receipt:correction-api:another-cancel"},
        ):
            with self.subTest(changes=changes):
                payload = {
                    **self.payload,
                    **changes,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("detail", response.data)

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(self.payment.history.count(), 1)
        self.assertEqual(
            self.payment.history.get().comment,
            self.payload["comment"],
        )
