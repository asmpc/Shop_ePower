from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.models import AccountTransactionType
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import (
    OrderItem,
    OrderStatus,
)
from shop_epower.orders.services import complete_order_shipment
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from shop_epower.payments.services import record_manual_order_payment


class TestsOrderFundAssignmentAPI(TestCase):
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
        self.payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="assignment:api:receipt:001",
            created_by=self.manager,
        )
        self.url = reverse(
            "api_orders:manage-assign-funds",
            kwargs={"order_id": self.order.pk},
        )
        self.payload = {
            "amount": "60.00",
            "operation_key": "assignment:api:assign:001",
            "comment": "Prepayment assigned to the order.",
        }

    # Менеджер назначает заказу часть уже поступивших денег.
    # До отгрузки уменьшается только доступный баланс.
    # Новое поступление, долг и отгрузка не создаются.
    def test_manager_can_assign_funds_before_shipment(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        assignment = self.order.fund_assignments.get()
        transaction = assignment.account_transaction
        source = assignment.sources.get()

        self.assertEqual(response.data["id"], assignment.pk)
        self.assertEqual(assignment.amount, Decimal("60.00"))
        self.assertEqual(
            transaction.operation_type,
            AccountTransactionType.FUNDS_ASSIGNMENT,
        )
        self.assertEqual(
            transaction.available_delta,
            Decimal("-60.00"),
        )
        self.assertEqual(transaction.debt_delta, Decimal("0.00"))
        self.assertEqual(transaction.created_by_id, self.manager.pk)
        self.assertEqual(
            transaction.operation_key,
            self.payload["operation_key"],
        )
        self.assertEqual(transaction.comment, self.payload["comment"])
        self.assertEqual(
            source.deposit_transaction_id,
            self.payment.deposit_transaction_id,
        )
        self.assertEqual(source.amount, Decimal("60.00"))

        self.account.refresh_from_db()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertFalse(assignment.applications.exists())
        self.assertFalse(self.order.shipments.exists())

    # Клиент не может назначить деньги даже своему заказу.
    # Прямой запрос запрещён, доступный баланс не уменьшается.
    def test_customer_cannot_assign_order_funds(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.account.refresh_from_db()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)

    # Повтор одного запроса возвращает существующее назначение.
    # Деньги списываются один раз, источник назначения не дублируется.
    def test_repeated_assignment_request_debits_account_once(self):
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

        assignment = self.order.fund_assignments.get()

        self.assertEqual(assignment.amount, Decimal("60.00"))
        self.assertEqual(assignment.sources.count(), 1)
        self.assertEqual(
            assignment.sources.get().amount,
            Decimal("60.00"),
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertFalse(assignment.applications.exists())

    # Использованный ключ нельзя применить к другой сумме.
    # Первоначальное назначение и его финансовый результат сохраняются.
    def test_assignment_rejects_same_key_with_different_amount(self):
        self.client.force_authenticate(user=self.manager)

        first_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )
        self.assertEqual(first_response.status_code, 201)

        changed_payload = self.payload.copy()
        changed_payload["amount"] = "30.00"

        response = self.client.post(
            self.url,
            changed_payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

        assignment = self.order.fund_assignments.get()

        self.assertEqual(assignment.pk, first_response.data["id"])
        self.assertEqual(assignment.amount, Decimal("60.00"))
        self.assertEqual(
            assignment.sources.get().amount,
            Decimal("60.00"),
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(Payment.objects.count(), 1)

    # После отгрузки администратор назначает деньги заказу
    # и погашает соответствующую часть долга.
    # Отгрузка сохраняется, новое поступление не создаётся.
    def test_admin_can_assign_funds_after_shipment(self):
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        product = create_test_product()
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )

        admin = create_test_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        assignment = self.order.fund_assignments.get()
        application = assignment.applications.get()

        self.assertEqual(response.data["id"], assignment.pk)
        self.assertEqual(assignment.amount, Decimal("60.00"))
        self.assertEqual(application.amount, Decimal("60.00"))
        self.assertEqual(application.shipment_id, shipment.pk)
        self.assertEqual(
            assignment.account_transaction.created_by_id,
            admin.pk,
        )
        self.assertEqual(
            application.account_transaction.created_by_id,
            admin.pk,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.shipments.get().pk, shipment.pk)
        self.assertEqual(self.account.transactions.count(), 4)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)

    # При нехватке доступных денег назначение отклоняется целиком.
    # Баланс, исходное поступление и финансовая история не меняются.
    def test_assignment_rejects_insufficient_available_funds(self):
        self.order.total_price = Decimal("200.00")
        self.order.save(update_fields=["total_price"])

        self.client.force_authenticate(user=self.manager)

        payload = self.payload.copy()
        payload["amount"] = "110.00"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Resulting available balance cannot be negative.",
            response.data["detail"],
        )

        self.account.refresh_from_db()
        self.payment.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)

    # Достаточный баланс не разрешает назначить больше суммы заказа.
    # При отказе списание и финансовая запись полностью откатываются.
    def test_assignment_rejects_amount_above_order_total(self):
        self.order.total_price = Decimal("50.00")
        self.order.save(update_fields=["total_price"])

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Assignment exceeds the remaining order amount.",
            response.data["detail"],
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
        self.assertFalse(self.order.fund_assignments.exists())
        self.assertEqual(Payment.objects.count(), 1)

    # Нулевая сумма отклоняется сериализатором.
    # Назначение и финансовая операция не создаются.
    def test_assignment_rejects_zero_amount(self):
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

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())

    # Без ключа операции назначение не выполняется.
    # Доступные деньги и исходное поступление сохраняются.
    def test_assignment_requires_operation_key(self):
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

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())
