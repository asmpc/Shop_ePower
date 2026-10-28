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
from shop_epower.orders.services import (
    assign_order_funds,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from shop_epower.payments.services import record_manual_order_payment


class TestsOrderFundAssignmentCancelAPI(TestCase):
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
            operation_key="assignment:cancel-api:receipt",
            created_by=self.manager,
        )
        self.assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:cancel-api:assign",
            created_by=self.manager,
        )
        self.url = reverse(
            "api_orders:manage-cancel-fund-assignment",
            kwargs={"assignment_id": self.assignment.pk},
        )
        self.payload = {
            "operation_key": "assignment:cancel-api:cancel",
            "comment": "Assignment entered by mistake.",
        }

    # Менеджер отменяет выбранное назначение до отгрузки.
    # Деньги возвращаются в доступный баланс, а причина
    # и сотрудник сохраняются в обратной операции.
    # Исходное поступление и назначение остаются в истории.
    def test_manager_can_cancel_assignment_before_shipment(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        reversal = self.account.transactions.get(
            reversal_of=self.assignment.account_transaction,
        )

        self.assertEqual(
            response.data["assignment_id"],
            self.assignment.pk,
        )
        self.assertEqual(response.data["reversal_id"], reversal.pk)
        self.assertEqual(
            reversal.operation_type,
            AccountTransactionType.REVERSAL,
        )
        self.assertEqual(
            reversal.available_delta,
            Decimal("60.00"),
        )
        self.assertEqual(reversal.debt_delta, Decimal("0.00"))
        self.assertEqual(reversal.created_by_id, self.manager.pk)
        self.assertEqual(reversal.comment, self.payload["comment"])
        self.assertEqual(
            reversal.operation_key,
            self.payload["operation_key"],
        )

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
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )
        self.assertEqual(
            self.assignment.sources.get().amount,
            Decimal("60.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)

    # Причина из одних пробелов отклоняется.
    # Назначение сохраняется, деньги остаются закреплены за заказом.
    def test_cancellation_rejects_blank_comment(self):
        self.client.force_authenticate(user=self.manager)

        payload = self.payload.copy()
        payload["comment"] = "   "

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("comment", response.data)

        self.account.refresh_from_db()
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
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)

    # Клиент не может отменить назначение своего заказа.
    # Прямой запрос запрещён и не освобождает назначенные деньги.
    def test_customer_cannot_cancel_fund_assignment(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.account.refresh_from_db()
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
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)

    # Повтор отмены с тем же ключом возвращает прежний результат.
    # Деньги возвращаются один раз, обратная операция не дублируется.
    def test_repeated_cancellation_returns_funds_once(self):
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

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            first_response.data["reversal_id"],
            second_response.data["reversal_id"],
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
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.account.transactions.filter(
                reversal_of=self.assignment.account_transaction,
            ).count(),
            1,
        )
        self.assertEqual(Payment.objects.count(), 1)

    # Новая попытка отменить уже отменённое назначение запрещена.
    # Первоначальная обратная операция и её причина сохраняются.
    def test_new_cancellation_key_rejects_already_cancelled_assignment(self):
        self.client.force_authenticate(user=self.manager)

        first_response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )
        self.assertEqual(first_response.status_code, 200)

        changed_payload = self.payload.copy()
        changed_payload["operation_key"] = "assignment:cancel-api:second"
        changed_payload["comment"] = "Another cancellation attempt."

        response = self.client.post(
            self.url,
            changed_payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

        reversal = self.account.transactions.get(
            reversal_of=self.assignment.account_transaction,
        )

        self.assertEqual(
            reversal.pk,
            first_response.data["reversal_id"],
        )
        self.assertEqual(reversal.comment, self.payload["comment"])
        self.assertEqual(
            reversal.operation_key,
            self.payload["operation_key"],
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
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(Payment.objects.count(), 1)

    # После отгрузки администратор отменяет назначение.
    # Доступные средства и погашенная часть долга восстанавливаются.
    # Отгрузка, поступление и исходные записи остаются в истории.
    def test_admin_can_cancel_assignment_after_shipment(self):
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
        application = self.assignment.applications.get()

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("40.00"),
        )

        admin = create_test_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        assignment_reversal = self.account.transactions.get(
            reversal_of=self.assignment.account_transaction,
        )
        application_reversal = self.account.transactions.get(
            reversal_of=application.account_transaction,
        )

        self.assertEqual(
            response.data["assignment_id"],
            self.assignment.pk,
        )
        self.assertEqual(
            response.data["reversal_id"],
            assignment_reversal.pk,
        )

        for reversal in (assignment_reversal, application_reversal):
            self.assertEqual(reversal.created_by_id, admin.pk)
            self.assertEqual(reversal.comment, self.payload["comment"])

        self.account.refresh_from_db()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.shipments.get().pk, shipment.pk)
        self.assertEqual(
            self.assignment.applications.get().pk,
            application.pk,
        )
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 6)

    # Причину отмены необходимо передать явно.
    # При отсутствии поля назначение и балансы не меняются.
    def test_cancellation_requires_comment(self):
        self.client.force_authenticate(user=self.manager)

        payload = self.payload.copy()
        payload.pop("comment")

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("comment", response.data)

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
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )

    # Без ключа операции отмена не выполняется.
    # Деньги остаются назначенными заказу.
    def test_cancellation_requires_operation_key(self):
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
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )
