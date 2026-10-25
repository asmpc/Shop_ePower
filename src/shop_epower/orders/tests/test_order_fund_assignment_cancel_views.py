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
from shop_epower.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from shop_epower.payments.services import record_manual_order_payment


class TestsManagerOrderFundAssignmentCancelViews(TestCase):
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
            operation_key="assignment:cancel-view:receipt",
            created_by=self.manager,
        )
        self.assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="assignment:cancel-view:assign",
            created_by=self.manager,
        )
        self.url = reverse(
            "orders:manager_cancel_order_fund_assignment",
            kwargs={"pk": self.assignment.pk},
        )

    # Просмотр подтверждения отмены ничего не меняет.
    # Назначение сохраняется, поступление остаётся оплаченным.
    def test_manager_can_open_cancellation_form_without_changing_funds(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "orders/manage/fund_assignment_cancel_form.html",
        )
        self.assertEqual(
            response.context["assignment"].pk,
            self.assignment.pk,
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
            Decimal("0.00"),
        )
        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )

    # Для отмены назначения нужна обязательная причина.
    # Ключ операции скрыт, а изменить сумму отмены нельзя.
    def test_cancellation_form_requires_comment_and_contains_operation_key(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertEqual(
            set(form.fields),
            {"comment", "operation_key"},
        )
        self.assertTrue(form.fields["comment"].required)
        self.assertTrue(
            form.fields["operation_key"].widget.is_hidden,
        )
        self.assertTrue(
            form.initial["operation_key"],
        )

        self.assertContains(response, 'name="comment"')
        self.assertContains(response, 'name="operation_key"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    # Отмена назначения до отгрузки возвращает деньги
    # на доступный баланс, не отменяя поступление.
    # Причина и сотрудник сохраняются в обратной операции.
    def test_manager_can_cancel_assignment_before_shipment(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        comment = "Funds assigned to the wrong order."

        response = self.client.post(
            self.url,
            {
                "comment": comment,
                "operation_key": operation_key,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.account.refresh_from_db()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assignment.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        reversal = self.account.transactions.get(
            reversal_of=self.assignment.account_transaction,
        )

        self.assertEqual(
            reversal.operation_type,
            AccountTransactionType.REVERSAL,
        )
        self.assertEqual(
            reversal.available_delta,
            Decimal("60.00"),
        )
        self.assertEqual(
            reversal.debt_delta,
            Decimal("0.00"),
        )
        self.assertEqual(reversal.comment, comment)
        self.assertEqual(reversal.created_by, self.manager)
        self.assertEqual(reversal.operation_key, operation_key)

        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )

    # Причина из одних пробелов не допускается.
    # Форма показывает ошибку, а деньги и история не меняются.
    def test_cancellation_rejects_blank_comment(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )

        response = self.client.post(
            self.url,
            {
                "comment": "   ",
                "operation_key": operation_key,
            },
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertTrue(form.is_bound)
        self.assertIn("comment", form.errors)
        self.assertEqual(
            form["operation_key"].value(),
            operation_key,
        )

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
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )

    # Клиент не может отменить назначение своего заказа
    # прямым запросом. Балансы и история остаются прежними.
    def test_customer_cannot_cancel_fund_assignment(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "comment": "Cancel this assignment.",
                "operation_key": "assignment:cancel-view:forbidden",
            },
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
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(
            self.order.fund_assignments.get().pk,
            self.assignment.pk,
        )

    # Повторная отправка с тем же ключом операции безопасна:
    # деньги возвращаются один раз, обратная операция одна.
    def test_repeated_cancellation_returns_funds_once(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        data = {
            "comment": "Assignment entered by mistake.",
            "operation_key": operation_key,
        }

        first_response = self.client.post(self.url, data)
        second_response = self.client.post(self.url, data)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)

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
        self.assertEqual(self.account.transactions.count(), 3)
        self.assertEqual(
            self.account.transactions.filter(
                reversal_of=self.assignment.account_transaction,
            ).count(),
            1,
        )
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)

    # После отгрузки отмена назначения восстанавливает
    # доступный баланс и долг. Отгрузка и поступление сохраняются.
    # Обе обратные операции содержат причину и администратора.
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
        self.client.force_login(admin)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        comment = "Cancel incorrect shipment settlement."

        response = self.client.post(
            self.url,
            {
                "comment": comment,
                "operation_key": operation_key,
            },
        )

        self.assertEqual(response.status_code, 302)

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

        assignment_reversal = self.account.transactions.get(
            reversal_of=self.assignment.account_transaction,
        )
        application_reversal = self.account.transactions.get(
            reversal_of=application.account_transaction,
        )

        self.assertEqual(
            assignment_reversal.available_delta,
            Decimal("60.00"),
        )
        self.assertEqual(
            application_reversal.debt_delta,
            Decimal("60.00"),
        )
        for reversal in (assignment_reversal, application_reversal):
            self.assertEqual(reversal.comment, comment)
            self.assertEqual(reversal.created_by, admin)

        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.shipments.get().pk, shipment.pk)
        self.assertEqual(
            self.assignment.applications.get().pk,
            application.pk,
        )
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 6)

    # На форме есть явная кнопка подтверждения отмены.
    # Просмотр страницы сам по себе отмену не выполняет.
    def test_cancellation_form_contains_confirmation_button(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                '<button type="submit" class="btn btn-danger">'
                "Cancel assignment"
                "</button>"
            ),
            html=True,
        )

    # Ссылка отмены относится к выбранному назначению
    # и сохраняет фильтр и страницу исходного списка заказов.
    def test_order_detail_links_to_cancellation_form_with_list_context(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=new&page=2"
        )
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )

        response = self.client.get(
            detail_url,
            {"next": list_url},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{self.url}?next={quote(list_url)}"',
        )
        self.assertContains(response, "Cancel assignment")

    # Из формы можно вернуться к заказу без отмены назначения.
    # Адрес исходного списка сохраняет фильтр и страницу.
    def test_cancellation_form_links_back_to_order_with_list_context(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=new&page=2"
        )
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )

        response = self.client.get(
            self.url,
            {"next": list_url},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{detail_url}?next={quote(list_url)}"',
        )
        self.assertContains(response, "Back to order")

    # Форма передаёт исходный список через скрытое поле.
    # После отмены возвращаемся к заказу с тем же контекстом.
    def test_cancellation_submission_preserves_order_list_context(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=new&page=2"
        )
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
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
                "comment": "Incorrect assignment.",
                "operation_key": operation_key,
                "next": list_url,
            },
        )

        self.assertRedirects(
            response,
            f"{detail_url}?{urlencode({'next': list_url})}",
            fetch_redirect_response=False,
        )

    # Отменённое назначение остаётся в истории с причиной.
    # Ссылка повторной отмены для него не отображается.
    def test_cancelled_assignment_has_no_cancellation_link(self):
        comment = "Assignment cancelled after checking the order."
        cancel_order_fund_assignment(
            assignment=self.assignment,
            operation_key="assignment:cancel-view:history",
            created_by=self.manager,
            comment=comment,
        )

        self.client.force_login(self.manager)
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"Assignment #{self.assignment.pk}",
        )
        self.assertContains(
            response,
            '<span class="badge bg-secondary">CANCELLED</span>',
            html=True,
        )
        self.assertContains(response, comment)
        self.assertNotContains(
            response,
            f'href="{self.url}?',
        )

    # Новая попытка отменить уже отменённое назначение
    # показывает ошибку и не возвращает деньги повторно.
    # Первоначальная причина отмены сохраняется.
    def test_cancellation_with_new_key_rejects_already_cancelled_assignment(self):
        original_comment = "Original cancellation reason."
        original_reversal = cancel_order_fund_assignment(
            assignment=self.assignment,
            operation_key="assignment:cancel-view:original",
            created_by=self.manager,
            comment=original_comment,
        )

        self.client.force_login(self.manager)
        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )

        self.assertNotEqual(
            operation_key,
            original_reversal.operation_key,
        )

        response = self.client.post(
            self.url,
            {
                "comment": "Another cancellation attempt.",
                "operation_key": operation_key,
            },
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertTrue(form.non_field_errors())
        self.assertEqual(
            form["operation_key"].value(),
            operation_key,
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

        reversal = self.account.transactions.get(
            reversal_of=self.assignment.account_transaction,
        )

        self.assertEqual(reversal.pk, original_reversal.pk)
        self.assertEqual(reversal.comment, original_comment)
