from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import AccountTransactionActorType
from shop_epower.finance.services import (
    create_personal_customer_account,
    record_customer_debt,
)
from shop_epower.payments.models import (
    CustomerPayout,
    PaymentMethod,
    PayoutMethod,
)
from shop_epower.payments.services import record_manual_account_payment


class TestsManagerAccountPayoutAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )

        self.receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:payout:api:receipt",
            created_by=self.manager,
        )

        self.url = reverse(
            "api-payments:manager-record-account-payout",
            kwargs={"account_id": self.account.pk},
        )

        self.payload = {
            "amount": "40.00",
            "method": PayoutMethod.CASH,
            "comment": "Money returned to the customer.",
            "operation_key": "account:payout:api:001",
        }

    # Проверяем подтверждение выплаты менеджером через API:
    # ответ содержит документ, счёт, сумму, статус и автора;
    # баланс уменьшается, долг не меняется, источник сохраняется.
    def test_manager_can_record_account_payout(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        payout = CustomerPayout.objects.get()

        self.assertEqual(response.data["id"], payout.pk)
        self.assertEqual(
            response.data["customer_account_id"],
            self.account.pk,
        )
        self.assertEqual(response.data["amount"], "40.00")
        self.assertEqual(response.data["method"], PayoutMethod.CASH)
        self.assertEqual(response.data["status"], "returned")
        self.assertEqual(
            response.data["performed_by"],
            self.manager.username,
        )
        self.assertEqual(
            response.data["comment"],
            self.payload["comment"],
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

        source = payout.sources.get()

        self.assertEqual(
            source.deposit_transaction_id,
            self.receipt.deposit_transaction_id,
        )
        self.assertEqual(source.amount, Decimal("40.00"))

    # Проверяем обязательную причину выплаты:
    # пустая строка и пробелы дают ошибку поля comment,
    # деньги и история остаются без изменений.
    def test_payout_requires_nonblank_reason(self):
        self.client.force_authenticate(user=self.manager)

        for comment in ("", "   "):
            with self.subTest(comment=comment):
                payload = {
                    **self.payload,
                    "comment": comment,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("comment", response.data)

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем запрет выплаты клиентом через API:
    # даже для собственного счёта запрос возвращает 403,
    # баланс и история не меняются.
    def test_customer_cannot_record_payout(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем запрет выплаты без авторизации:
    # API возвращает 401, деньги и история не меняются.
    def test_anonymous_user_cannot_record_payout(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 401)

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем банковскую выплату администратором:
    # способ поступления не ограничивает способ возврата,
    # в истории сохраняются автор и роль администратора.
    def test_admin_can_record_bank_payout(self):
        admin = create_test_admin()

        payload = {
            **self.payload,
            "method": PayoutMethod.BANK_TRANSFER,
            "comment": "Bank payout confirmed by administrator.",
        }

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["method"],
            PayoutMethod.BANK_TRANSFER,
        )
        self.assertEqual(
            response.data["performed_by"],
            admin.username,
        )

        payout = CustomerPayout.objects.get()

        self.assertEqual(payout.method, PayoutMethod.BANK_TRANSFER)
        self.assertEqual(
            payout.account_transaction.created_by_id,
            admin.pk,
        )
        self.assertEqual(
            payout.account_transaction.actor_type,
            AccountTransactionActorType.ADMIN,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем обязательный ключ операции:
    # отсутствие, null, пустое значение, пробелы и превышение длины
    # дают ошибку поля operation_key без изменения денег.
    def test_payout_requires_valid_operation_key(self):
        base_payload = self.payload.copy()
        base_payload.pop("operation_key")

        self.client.force_authenticate(user=self.manager)

        for key_fields in (
            {},
            {"operation_key": None},
            {"operation_key": ""},
            {"operation_key": "   "},
            {"operation_key": "x" * 256},
        ):
            with self.subTest(key_fields=key_fields):
                payload = {
                    **base_payload,
                    **key_fields,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("operation_key", response.data)

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем запрет выплаты при долге:
    # API возвращает понятную причину отказа,
    # документ выплаты не создаётся, балансы не меняются.
    def test_payout_is_forbidden_when_account_has_debt(self):
        record_customer_debt(
            account=self.account,
            amount=Decimal("60.00"),
            operation_key="account:payout:api:shipment-debt",
            actor_type=AccountTransactionActorType.MANAGER,
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
            "Customer account debt must be settled before payout.",
        )

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("60.00"),
        )

    # Проверяем запрет выплаты сверх свободного остатка:
    # API возвращает 400, частичная выплата не выполняется,
    # баланс и история остаются прежними.
    def test_payout_cannot_exceed_available_balance(self):
        payload = {
            **self.payload,
            "amount": "100.01",
        }

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Resulting available balance cannot be negative.",
        )

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем повтор запроса с тем же ключом и данными:
    # API возвращает прежний результат,
    # повторного списания и дублирования источников нет.
    def test_repeated_payout_does_not_debit_twice(self):
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

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(repeated_response.status_code, 201)
        self.assertEqual(repeated_response.data, first_response.data)

        payout = CustomerPayout.objects.get()

        self.assertEqual(repeated_response.data["id"], payout.pk)
        self.assertEqual(payout.sources.count(), 1)

        self.account.refresh_from_db()

        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем конфликт ключа при изменении суммы:
    # API отклоняет запрос, исходная выплата,
    # её источник и баланс остаются без изменений.
    def test_same_key_with_different_amount_is_rejected(self):
        self.client.force_authenticate(user=self.manager)

        first_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, 201)

        changed_payload = {
            **self.payload,
            "amount": "50.00",
        }

        response = self.client.post(
            self.url,
            changed_payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Operation key is already used for different transaction data.",
        )

        payout = CustomerPayout.objects.get()

        self.assertEqual(payout.pk, first_response.data["id"])
        self.assertEqual(payout.amount, Decimal("40.00"))
        self.assertEqual(payout.sources.get().amount, Decimal("40.00"))

        self.account.refresh_from_db()

        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем выплату по отсутствующему счёту:
    # авторизованный менеджер получает 404,
    # существующий счёт и его история не меняются.
    def test_missing_account_returns_404(self):
        missing_url = reverse(
            "api-payments:manager-record-account-payout",
            kwargs={"account_id": self.account.pk + 1},
        )

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            missing_url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 404)

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем некорректные суммы:
    # отсутствие, null, ноль, отрицательное значение,
    # лишняя точность, неверный формат и переполнение дают 400.
    # Деньги и история остаются без изменений.
    def test_invalid_amount_is_rejected_without_changes(self):
        base_payload = self.payload.copy()
        base_payload.pop("amount")

        self.client.force_authenticate(user=self.manager)

        for amount_fields in (
            {},
            {"amount": None},
            {"amount": "0.00"},
            {"amount": "-1.00"},
            {"amount": "1.001"},
            {"amount": "not-a-number"},
            {"amount": "NaN"},
            {"amount": "Infinity"},
            {"amount": "10000000000000000.00"},
        ):
            with self.subTest(amount_fields=amount_fields):
                payload = {
                    **base_payload,
                    **amount_fields,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("amount", response.data)

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Проверяем недопустимые способы возврата:
    # онлайн-возврат, коды способов поступления и неизвестное значение
    # дают ошибку поля method без изменения денег и истории.
    def test_unsupported_payout_method_is_rejected(self):
        self.client.force_authenticate(user=self.manager)

        for method in (
            PaymentMethod.ONLINE,
            PaymentMethod.ON_RECEIPT,
            PaymentMethod.INVOICE,
            "unknown",
        ):
            with self.subTest(method=method):
                payload = {
                    **self.payload,
                    "method": method,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("method", response.data)

        self.account.refresh_from_db()

        self.assertFalse(CustomerPayout.objects.exists())
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
