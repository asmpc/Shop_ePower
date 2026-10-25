from decimal import Decimal
from urllib.parse import quote, urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

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
    cancel_order_fund_assignment,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import Payment, PaymentMethod
from shop_epower.payments.services import record_manual_order_payment


class TestsManagerOrderFundAssignmentViews(TestCase):
    def setUp(self):
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
            operation_key="assignment:view:receipt:001",
            created_by=self.manager,
        )
        self.url = reverse(
            "orders:manager_assign_order_funds",
            kwargs={"pk": self.order.pk},
        )

    def _create_assignments(self, count):
        assignments = []

        for index in range(count):
            assignment = assign_order_funds(
                order=self.order,
                amount=Decimal("1.00"),
                operation_key=f"assignment:view:page:{index}",
                created_by=self.manager,
            )
            assignments.append(assignment)

        return assignments

    # Менеджер может открыть форму назначения полученных денег.
    # Просмотр не меняет балансы и статус заказа,
    # не создаёт назначение или дополнительный платёж.
    def test_manager_can_open_assignment_form_without_changing_funds(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "orders/manage/fund_assignment_form.html",
        )
        self.assertEqual(response.context["order"].pk, self.order.pk)

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.order.payments.get().pk, self.payment.pk)
        self.assertFalse(self.order.fund_assignments.exists())

    # Форма назначения содержит сумму, комментарий и скрытый ключ.
    # Способ поступления не выбирается: используются уже полученные деньги.
    def test_assignment_form_contains_fields_and_operation_key(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="amount"')
        self.assertContains(response, 'name="comment"')
        self.assertContains(response, 'name="operation_key"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

        form = response.context["form"]

        self.assertEqual(
            set(form.fields),
            {"amount", "comment", "operation_key"},
        )
        self.assertTrue(form.fields["operation_key"].widget.is_hidden)
        self.assertTrue(form.initial.get("operation_key"))

    # Менеджер назначает полученные деньги заказу до отгрузки.
    # Доступный баланс уменьшается, долг не возникает.
    # Новое поступление и применение к долгу не создаются.
    def test_manager_can_assign_funds_before_shipment(self):
        self.client.force_login(self.manager)
        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        comment = "Prepayment assigned to the order."

        response = self.client.post(
            self.url,
            {
                "amount": "60.00",
                "operation_key": operation_key,
                "comment": comment,
            },
        )

        self.assertEqual(response.status_code, 302)

        assignment = self.order.fund_assignments.get()
        account_transaction = assignment.account_transaction

        self.assertEqual(assignment.amount, Decimal("60.00"))
        self.assertEqual(
            account_transaction.operation_type,
            AccountTransactionType.FUNDS_ASSIGNMENT,
        )
        self.assertEqual(
            account_transaction.available_delta,
            Decimal("-60.00"),
        )
        self.assertEqual(
            account_transaction.debt_delta,
            Decimal("0.00"),
        )
        self.assertEqual(account_transaction.operation_key, operation_key)
        self.assertEqual(account_transaction.created_by_id, self.manager.pk)
        self.assertEqual(account_transaction.comment, comment)

        source = assignment.sources.get()
        self.assertEqual(
            source.deposit_transaction_id,
            self.payment.deposit_transaction_id,
        )
        self.assertEqual(source.amount, Decimal("60.00"))

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.order.payments.get().pk, self.payment.pk)
        self.assertFalse(assignment.applications.exists())
        self.assertFalse(self.order.shipments.exists())

    # Клиент не может назначать деньги даже своему заказу.
    # Прямой POST возвращает 403 и не изменяет доступные средства.
    def test_customer_cannot_assign_order_funds(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "amount": "60.00",
                "operation_key": "order-fund-assignment:forbidden",
                "comment": "Attempted assignment.",
            },
        )

        self.assertEqual(response.status_code, 403)

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.order.payments.get().pk, self.payment.pk)
        self.assertFalse(self.order.fund_assignments.exists())

    # После отгрузки администратор назначает доступные деньги заказу.
    # Назначение уменьшает доступный баланс и погашает долг отгрузки.
    # Заказ остаётся завершённым, новое поступление не создаётся.
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

        admin = create_test_admin()
        self.client.force_login(admin)
        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )

        response = self.client.post(
            self.url,
            {
                "amount": "60.00",
                "operation_key": operation_key,
                "comment": "Partial settlement of shipment debt.",
            },
        )

        self.assertEqual(response.status_code, 302)

        assignment = self.order.fund_assignments.get()
        application = assignment.applications.get()

        self.assertEqual(assignment.amount, Decimal("60.00"))
        self.assertEqual(application.shipment_id, shipment.pk)
        self.assertEqual(application.amount, Decimal("60.00"))
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
        self.assertEqual(self.order.payments.get().pk, self.payment.pk)

    # Повторная отправка формы не создаёт второе назначение
    # и не списывает доступные деньги повторно.
    def test_repeated_assignment_submission_debits_account_once(self):
        self.client.force_login(self.manager)
        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        data = {
            "amount": "60.00",
            "operation_key": operation_key,
            "comment": "Prepayment assigned to the order.",
        }

        first_response = self.client.post(self.url, data)
        repeated_response = self.client.post(self.url, data)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(repeated_response.status_code, 302)
        self.assertEqual(self.order.fund_assignments.count(), 1)

        assignment = self.order.fund_assignments.get()

        self.assertEqual(assignment.sources.count(), 1)
        self.assertEqual(
            assignment.account_transaction.operation_key,
            operation_key,
        )
        self.assertFalse(assignment.applications.exists())

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(Payment.objects.count(), 1)

    # Недостаточный баланс отклоняется сервисом без списания денег.
    # Форма показывает ошибку и сохраняет сумму и ключ операции.
    def test_insufficient_funds_preserves_assignment_form(self):
        self.order.total_price = Decimal("200.00")
        self.order.save(update_fields=["total_price"])

        self.client.force_login(self.manager)
        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )

        response = self.client.post(
            self.url,
            {
                "amount": "110.00",
                "operation_key": operation_key,
                "comment": "Prepayment assigned to the order.",
            },
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertTrue(form.is_bound)
        self.assertNotIn("amount", form.errors)
        self.assertIn(
            "Resulting available balance cannot be negative.",
            form.non_field_errors(),
        )
        self.assertEqual(form["amount"].value(), "110.00")
        self.assertEqual(
            form["operation_key"].value(),
            operation_key,
        )

        self.account.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertFalse(self.order.fund_assignments.exists())

    # Со страницы заказа можно открыть форму назначения денег.
    # Ссылка сохраняет исходный список с фильтром и страницей.
    def test_order_detail_links_to_assignment_form_with_list_context(self):
        self.client.force_login(self.manager)
        list_url = (
            f"{reverse('orders:manager_order_list')}"
            "?status=new&page=2"
        )

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
            {"next": list_url},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assign funds")
        self.assertContains(
            response,
            f'href="{self.url}?next={quote(list_url)}"',
        )

    # Форма передаёт исходный список скрытым полем.
    # После назначения заказ открывается с прежним контекстом возврата.
    def test_assignment_submission_preserves_order_list_context(self):
        self.client.force_login(self.manager)
        list_url = (
            f"{reverse('orders:manager_order_list')}"
            "?status=new&page=2"
        )

        form_response = self.client.get(
            self.url,
            {"next": list_url},
        )

        self.assertContains(
            form_response,
            (
                '<input type="hidden" name="next" '
                f'value="{escape(list_url)}">'
            ),
            html=True,
        )

        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        response = self.client.post(
            self.url,
            {
                "amount": "60.00",
                "operation_key": operation_key,
                "comment": "",
                "next": list_url,
            },
        )

        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )
        self.assertRedirects(
            response,
            f"{detail_url}?{urlencode({'next': list_url})}",
            fetch_redirect_response=False,
        )

    # Из формы можно вернуться к заказу без назначения денег.
    # Исходный список с фильтром и страницей сохраняется.
    def test_assignment_form_links_back_to_order_with_list_context(self):
        self.client.force_login(self.manager)
        list_url = (
            f"{reverse('orders:manager_order_list')}"
            "?status=new&page=2"
        )

        response = self.client.get(
            self.url,
            {"next": list_url},
        )

        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Back to order")
        self.assertContains(
            response,
            f'href="{detail_url}?next={quote(list_url)}"',
        )

    # Страница заказа получает историю назначений через пагинатор.
    # Размер страницы — 20 записей.
    def test_order_detail_contains_paginated_assignment_history(self):
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:view:history",
            created_by=self.manager,
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)

        page = response.context["fund_assignments"]

        self.assertEqual(list(page), [assignment])
        self.assertEqual(page.paginator.per_page, 20)
        self.assertEqual(page.number, 1)

    # На странице заказа видны сумма, автор и комментарий назначения.
    # Действующее назначение явно отмечено статусом ACTIVE.
    def test_order_detail_displays_active_fund_assignment(self):
        comment = "Prepayment for order history."
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:view:history:active",
            created_by=self.manager,
            comment=comment,
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fund assignments")
        self.assertContains(response, f"Assignment #{assignment.pk}")
        self.assertContains(
            response,
            '<span class="badge bg-success">ACTIVE</span>',
            html=True,
        )
        self.assertContains(response, f"60.00 {self.account.currency}")
        self.assertContains(response, self.manager.email)
        self.assertContains(response, comment)

    # Отменённое назначение остаётся в истории.
    # Видны исходный комментарий, причина отмены
    # и разные авторы назначения и отмены.
    def test_order_detail_displays_assignment_cancellation_details(self):
        original_comment = "Original assignment retained."
        cancellation_comment = "Funds were assigned to the wrong order."

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:view:history:before-cancel",
            created_by=self.manager,
            comment=original_comment,
        )
        admin = create_test_admin()
        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key="assignment:view:history:cancel",
            created_by=admin,
            comment=cancellation_comment,
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Assignment #{assignment.pk}")
        self.assertContains(
            response,
            '<span class="badge bg-secondary">CANCELLED</span>',
            html=True,
        )
        self.assertContains(response, original_comment)
        self.assertContains(response, cancellation_comment)
        self.assertContains(response, self.manager.email)
        self.assertContains(response, admin.email)

    # История назначений разделяется на страницы по 20 записей.
    # На второй странице остаётся самое старое назначение.
    def test_assignment_history_is_paginated(self):
        assignments = self._create_assignments(21)

        for index in range(21):
            assignment = assign_order_funds(
                order=self.order,
                amount=Decimal("1.00"),
                operation_key=f"assignment:view:page:{index}",
                created_by=self.manager,
            )
            assignments.append(assignment)

        self.client.force_login(self.manager)
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )

        first_response = self.client.get(detail_url)
        second_response = self.client.get(
            detail_url,
            {"assignments_page": 2},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        first_page = first_response.context["fund_assignments"]
        second_page = second_response.context["fund_assignments"]

        self.assertEqual(first_page.paginator.count, 21)
        self.assertEqual(len(first_page), 20)
        self.assertTrue(first_page.has_next())
        self.assertEqual(list(second_page), [assignments[0]])
        self.assertFalse(second_page.has_next())

    # Ссылки пагинации истории сохраняют исходный список заказов.
    # Переходы вперёд и назад меняют только страницу назначений.
    def test_assignment_pagination_links_preserve_list_context(self):
        self._create_assignments(21)
        self.client.force_login(self.manager)
        list_url = (
            f"{reverse('orders:manager_order_list')}"
            "?status=new&page=2"
        )
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )

        first_response = self.client.get(
            detail_url,
            {"next": list_url},
        )
        next_query = urlencode(
            {
                "next": list_url,
                "assignments_page": 2,
            },
        )

        self.assertContains(
            first_response,
            f'href="?{escape(next_query)}"',
        )

        second_response = self.client.get(
            detail_url,
            {
                "next": list_url,
                "assignments_page": 2,
            },
        )
        previous_query = urlencode(
            {
                "next": list_url,
                "assignments_page": 1,
            },
        )

        self.assertContains(
            second_response,
            f'href="?{escape(previous_query)}"',
        )
