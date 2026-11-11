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
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.payments.models import (
    Invoice,
    Payment,
    PaymentMethod,
    PaymentStatus,
)


class TestsManagerAccountReceiptRegistrationAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

        self.url = reverse(
            "api-payments:manager-record-account-receipt",
            kwargs={"account_id": self.account.pk},
        )
        self.payload = {
            "amount": "100.00",
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "account:receipt:api:001",
            "comment": "Advance received in the office.",
        }

    # Менеджер регистрирует поступление на счёт клиента без заказов.
    # Создаются оплаченный Payment и одно пополнение.
    # Долг, заказ и Invoice автоматически не создаются.
    def test_manager_can_record_receipt_without_order(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        payment = Payment.objects.get()

        self.assertEqual(response.data["id"], payment.pk)
        self.assertIsNone(response.data["order"])
        self.assertEqual(response.data["status"], PaymentStatus.PAID)
        self.assertEqual(
            response.data["customer_account_id"],
            self.account.pk,
        )
        self.assertEqual(
            payment.deposit_transaction.account_id,
            self.account.pk,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.user.orders.exists())
        self.assertFalse(Invoice.objects.exists())

    # Клиент не может зарегистрировать поступление на собственный счёт.
    # Отказ не создаёт платёж или финансовую операцию и не меняет баланс.
    def test_customer_cannot_record_receipt_for_own_account(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

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

    # Повтор запроса с тем же ключом возвращает прежний Payment.
    # Второй платёж и повторное зачисление не создаются.
    def test_repeated_request_does_not_double_credit_account(self):
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
        self.assertEqual(
            repeated_response.data["id"],
            first_response.data["id"],
        )

        self.account.refresh_from_db()

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

    # Тот же ключ с изменённой суммой возвращает 400.
    # Первоначальные платёж, пополнение и баланс сохраняются.
    def test_reused_key_with_changed_amount_returns_400(self):
        self.client.force_authenticate(user=self.manager)

        first_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )
        self.assertEqual(first_response.status_code, 201)

        self.payload["amount"] = "150.00"

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

        self.account.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(
            Payment.objects.get().amount,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Сумма, не помещающаяся в поле Payment.amount,
    # отклоняется сериализатором без денежных изменений.
    def test_too_large_amount_returns_400_without_credit(self):
        self.payload["amount"] = "10000000000.00"

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("amount", response.data)

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

    # Администратор регистрирует безнал без заказа и Invoice.
    # Финансовая операция сохраняет его роль и идентификатор.
    def test_admin_can_record_bank_receipt_without_invoice(self):
        admin = create_test_admin()
        self.payload["method"] = PaymentMethod.INVOICE

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        payment = Payment.objects.get()
        deposit = payment.deposit_transaction

        self.assertEqual(payment.method, PaymentMethod.INVOICE)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(deposit.created_by_id, admin.pk)
        self.assertEqual(
            deposit.actor_type,
            AccountTransactionActorType.ADMIN,
        )
        self.assertFalse(self.user.orders.exists())
        self.assertFalse(Invoice.objects.exists())

        self.account.refresh_from_db()

        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Регистрация на несуществующий счёт возвращает 404.
    # Платёж и финансовая операция не создаются.
    def test_nonexistent_account_returns_404_without_credit(self):
        self.client.force_authenticate(user=self.manager)

        url = reverse(
            "api-payments:manager-record-account-receipt",
            kwargs={"account_id": 999999},
        )

        response = self.client.post(
            url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 404)

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

    # Неавторизованный запрос не может зарегистрировать поступление.
    # Платёж, финансовая операция и изменение баланса отсутствуют.
    def test_anonymous_user_cannot_record_receipt(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 401)

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
