from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import AccountTransactionType
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderStatus
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
)


class TestsManagerPaymentReceiptAPI(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.NEW,
            total_price=Decimal("100.00"),
        )
        self.url = reverse(
            "api-payments:manager-record-receipt",
            kwargs={"order_id": self.order.pk},
        )
        self.payload = {
            "amount": "60.00",
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": "receipt:api:office:001",
            "comment": "Money received at the office.",
        }

    # Менеджер регистрирует фактически полученные деньги.
    # Поступление пополняет доступный баланс, но не назначается
    # заказу автоматически и не создаёт Invoice.
    def test_manager_can_record_office_receipt(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        payment = Payment.objects.get(order=self.order)

        self.assertEqual(response.data["id"], payment.pk)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.method, PaymentMethod.ON_RECEIPT)
        self.assertEqual(payment.amount, Decimal("60.00"))
        self.assertIsNotNone(payment.deposit_transaction_id)

        deposit = payment.deposit_transaction

        self.assertEqual(
            deposit.operation_type,
            AccountTransactionType.DEPOSIT,
        )
        self.assertEqual(
            deposit.operation_key,
            self.payload["operation_key"],
        )
        self.assertEqual(deposit.created_by_id, self.manager.pk)
        self.assertEqual(deposit.comment, self.payload["comment"])

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertFalse(self.order.invoices.exists())

    # Клиент не может подтвердить поступление даже для своего заказа.
    # Прямой запрос запрещён и не создаёт платёж или пополнение.
    def test_customer_cannot_record_receipt(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
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
        self.assertFalse(self.order.fund_assignments.exists())

    # Повтор одного запроса с тем же ключом возвращает тот же платёж.
    # Поступление и пополнение баланса создаются только один раз.
    def test_repeated_receipt_request_credits_account_once(self):
        self.client.force_authenticate(user=self.manager)

        first_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )
        second_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(
            first_response.data["id"],
            second_response.data["id"],
        )

        self.account.refresh_from_db()

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.fund_assignments.exists())

    # Один ключ нельзя использовать для поступлений с разными данными.
    # Изменённая сумма отклоняется, первоначальный платёж сохраняется.
    def test_receipt_rejects_same_key_with_different_amount(self):
        self.client.force_authenticate(user=self.manager)

        first_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )
        self.assertEqual(first_response.status_code, 201)

        changed_payload = self.payload.copy()
        changed_payload["amount"] = "70.00"

        response = self.client.post(
            self.url,
            changed_payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Operation key is already used for different payment data.",
        )

        self.account.refresh_from_db()
        payment = Payment.objects.get(order=self.order)

        self.assertEqual(payment.pk, first_response.data["id"])
        self.assertEqual(payment.amount, Decimal("60.00"))
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Администратор может подтвердить поступление по безналу
    # без выставленного Invoice. Документ автоматически не создаётся,
    # а в финансовой истории сохраняется администратор.
    def test_admin_can_record_bank_receipt_without_invoice(self):
        admin = create_test_admin()
        self.client.force_authenticate(user=admin)

        payload = self.payload.copy()
        payload["method"] = PaymentMethod.INVOICE
        payload["operation_key"] = "receipt:api:bank:001"
        payload["comment"] = "Bank transfer received."

        self.assertFalse(self.order.invoices.exists())

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        payment = Payment.objects.get(order=self.order)
        deposit = payment.deposit_transaction

        self.assertEqual(response.data["id"], payment.pk)
        self.assertEqual(payment.method, PaymentMethod.INVOICE)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.amount, Decimal("60.00"))
        self.assertEqual(deposit.created_by_id, admin.pk)
        self.assertEqual(deposit.comment, payload["comment"])

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.invoices.exists())
        self.assertFalse(self.order.fund_assignments.exists())

    # Нулевая сумма отклоняется проверкой входных данных.
    # Платёж, финансовая операция и пополнение не создаются.
    def test_receipt_rejects_zero_amount(self):
        self.client.force_authenticate(user=self.manager)

        payload = self.payload.copy()
        payload["amount"] = "0.00"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("amount", response.data)

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.account.transactions.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Без ключа операции поступление не регистрируется.
    # Сервер не создаёт ключ вместо вызывающей стороны.
    def test_receipt_requires_operation_key(self):
        self.client.force_authenticate(user=self.manager)

        payload = self.payload.copy()
        payload.pop("operation_key")

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("operation_key", response.data)

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.account.transactions.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

    # Ручной API принимает только поступления офиса и безнала.
    # Онлайн-оплату нельзя подтвердить этим действием.
    def test_manual_receipt_rejects_online_method(self):
        self.client.force_authenticate(user=self.manager)

        payload = self.payload.copy()
        payload["method"] = PaymentMethod.ONLINE

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("method", response.data)

        self.account.refresh_from_db()

        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.account.transactions.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
