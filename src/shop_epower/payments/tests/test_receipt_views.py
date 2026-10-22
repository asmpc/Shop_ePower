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
from shop_epower.finance.models import (
    AccountTransactionActorType,
    AccountTransactionType,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)


class TestsManagerPaymentReceiptViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
            payment_method=PaymentMethod.ON_RECEIPT,
        )

    # Открытие формы регистрации поступления доступно менеджеру.
    # Просмотр формы не создаёт платёж, финансовую операцию
    # или назначение денег и не изменяет балансы.
    def test_manager_can_open_receipt_form_without_creating_payment(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "payments:manager_record_receipt",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "payments/manage/receipt_form.html",
        )
        self.assertEqual(response.context["order"].pk, self.order.pk)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(self.order.fund_assignments.exists())

    # Форма содержит сумму, ручной способ поступления, комментарий
    # и заранее созданный скрытый ключ защиты от повторной операции.
    # Онлайн-оплата в этой форме недоступна.
    def test_receipt_form_contains_fields_and_operation_key(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "payments:manager_record_receipt",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="amount"')
        self.assertContains(response, 'name="method"')
        self.assertContains(response, 'name="comment"')
        self.assertContains(response, 'name="operation_key"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

        form = response.context["form"]

        self.assertTrue(form.fields["operation_key"].widget.is_hidden)
        self.assertTrue(form.initial.get("operation_key"))
        self.assertEqual(
            {
                value
                for value, label in form.fields["method"].choices
            },
            {
                PaymentMethod.ON_RECEIPT,
                PaymentMethod.INVOICE,
            },
        )

    # Менеджер регистрирует фактически полученные в офисе деньги.
    # Создаются оплаченный платёж и одно пополнение счёта.
    # Назначение денег, долг и статус заказа не меняются.
    def test_manager_can_record_office_receipt(self):
        self.client.force_login(self.manager)
        url = reverse(
            "payments:manager_record_receipt",
            kwargs={"pk": self.order.pk},
        )
        form_response = self.client.get(url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        comment = "Payment received in the office."

        response = self.client.post(
            url,
            {
                "amount": "40.00",
                "method": PaymentMethod.ON_RECEIPT,
                "operation_key": operation_key,
                "comment": comment,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)

        payment = Payment.objects.get()
        deposit = self.account.transactions.get()

        self.assertEqual(payment.order_id, self.order.pk)
        self.assertEqual(payment.amount, Decimal("40.00"))
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.method, PaymentMethod.ON_RECEIPT)
        self.assertEqual(payment.provider, PaymentProvider.MANUAL)
        self.assertEqual(payment.manager_comment, comment)
        self.assertEqual(payment.deposit_transaction_id, deposit.pk)

        self.assertEqual(
            deposit.operation_type,
            AccountTransactionType.DEPOSIT,
        )
        self.assertEqual(deposit.operation_key, operation_key)
        self.assertEqual(deposit.available_delta, Decimal("40.00"))
        self.assertEqual(deposit.debt_delta, Decimal("0.00"))
        self.assertEqual(deposit.created_by_id, self.manager.pk)
        self.assertEqual(deposit.comment, comment)

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
        self.assertEqual(
            self.order.status,
            "new",
        )
        self.assertFalse(self.order.fund_assignments.exists())

    # Клиент не может зарегистрировать поступление прямым POST-запросом.
    # Сервер возвращает 403 и не создаёт финансовых записей.
    def test_customer_cannot_record_receipt(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "payments:manager_record_receipt",
                kwargs={"pk": self.order.pk},
            ),
            {
                "amount": "40.00",
                "method": PaymentMethod.ON_RECEIPT,
                "operation_key": "manual-receipt:forbidden",
                "comment": "Attempted receipt registration.",
            },
        )

        self.assertEqual(response.status_code, 403)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(self.order.fund_assignments.exists())

    # Повторная отправка формы с тем же ключом
    # не создаёт второй платёж и не пополняет счёт повторно.
    def test_repeated_receipt_submission_credits_account_once(self):
        self.client.force_login(self.manager)
        url = reverse(
            "payments:manager_record_receipt",
            kwargs={"pk": self.order.pk},
        )
        form_response = self.client.get(url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        data = {
            "amount": "40.00",
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": operation_key,
            "comment": "Payment received in the office.",
        }

        first_response = self.client.post(url, data)
        repeated_response = self.client.post(url, data)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(repeated_response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)

        payment = Payment.objects.get()
        deposit = self.account.transactions.get()

        self.assertEqual(payment.deposit_transaction_id, deposit.pk)
        self.assertEqual(deposit.operation_key, operation_key)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.fund_assignments.exists())

    # Администратор может зарегистрировать безналичное поступление.
    # Invoice не требуется и автоматически не создаётся.
    # Деньги пополняют доступный баланс без назначения заказу.
    def test_admin_can_record_bank_receipt_without_invoice(self):
        admin = create_test_admin()
        self.client.force_login(admin)
        url = reverse(
            "payments:manager_record_receipt",
            kwargs={"pk": self.order.pk},
        )
        form_response = self.client.get(url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )

        response = self.client.post(
            url,
            {
                "amount": "60.00",
                "method": PaymentMethod.INVOICE,
                "operation_key": operation_key,
                "comment": "Bank transfer received.",
            },
        )

        self.assertEqual(response.status_code, 302)

        payment = Payment.objects.get()
        deposit = self.account.transactions.get()

        self.assertEqual(payment.amount, Decimal("60.00"))
        self.assertEqual(payment.method, PaymentMethod.INVOICE)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.provider, PaymentProvider.MANUAL)
        self.assertEqual(payment.deposit_transaction_id, deposit.pk)
        self.assertEqual(
            deposit.actor_type,
            AccountTransactionActorType.ADMIN,
        )
        self.assertEqual(deposit.created_by_id, admin.pk)
        self.assertFalse(Invoice.objects.exists())

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.fund_assignments.exists())

    # Нулевая сумма отклоняется без создания поступления.
    # Форма сохраняет введённые данные и прежний ключ операции.
    def test_invalid_receipt_amount_preserves_form_and_operation_key(self):
        self.client.force_login(self.manager)
        url = reverse(
            "payments:manager_record_receipt",
            kwargs={"pk": self.order.pk},
        )
        form_response = self.client.get(url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        comment = "Payment received in the office."

        response = self.client.post(
            url,
            {
                "amount": "0.00",
                "method": PaymentMethod.ON_RECEIPT,
                "operation_key": operation_key,
                "comment": comment,
            },
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertTrue(form.is_bound)
        self.assertIn("amount", form.errors)
        self.assertEqual(form["amount"].value(), "0.00")
        self.assertEqual(form["comment"].value(), comment)
        self.assertEqual(
            form["operation_key"].value(),
            operation_key,
        )
        self.assertContains(response, f'value="{operation_key}"')

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(self.order.fund_assignments.exists())

    # Со страницы заказа можно открыть регистрацию поступления.
    # Ссылка сохраняет исходный список заказов с фильтром и страницей.
    def test_order_detail_links_to_receipt_form_with_list_context(self):
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

        receipt_url = reverse(
            "payments:manager_record_receipt",
            kwargs={"pk": self.order.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register receipt")
        self.assertContains(
            response,
            f'href="{receipt_url}?next={quote(list_url)}"',
        )

    # Форма сохраняет адрес исходного списка скрытым полем.
    # После регистрации поступления заказ открывается с тем же
    # контекстом возврата: фильтром и страницей списка.
    def test_receipt_registration_preserves_order_list_context(self):
        self.client.force_login(self.manager)
        list_url = (
            f"{reverse('orders:manager_order_list')}"
            "?status=new&page=2"
        )
        receipt_url = reverse(
            "payments:manager_record_receipt",
            kwargs={"pk": self.order.pk},
        )

        form_response = self.client.get(
            receipt_url,
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
            receipt_url,
            {
                "amount": "40.00",
                "method": PaymentMethod.ON_RECEIPT,
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

    # Из формы можно вернуться к заказу без регистрации поступления.
    # Адрес исходного списка с фильтром и страницей сохраняется.
    def test_receipt_form_links_back_to_order_with_list_context(self):
        self.client.force_login(self.manager)
        list_url = (
            f"{reverse('orders:manager_order_list')}"
            "?status=new&page=2"
        )

        response = self.client.get(
            reverse(
                "payments:manager_record_receipt",
                kwargs={"pk": self.order.pk},
            ),
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

    # Повтор ключа с изменённой суммой отклоняется сервисом.
    # Ошибка показывается в форме, исходное поступление не меняется.
    def test_receipt_key_conflict_shows_error_without_changing_payment(self):
        self.client.force_login(self.manager)
        url = reverse(
            "payments:manager_record_receipt",
            kwargs={"pk": self.order.pk},
        )
        form_response = self.client.get(url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        data = {
            "amount": "40.00",
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": operation_key,
            "comment": "Payment received in the office.",
        }

        first_response = self.client.post(url, data)
        self.assertEqual(first_response.status_code, 302)

        data["amount"] = "50.00"
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertIn(
            "Operation key is already used for different payment data.",
            form.non_field_errors(),
        )
        self.assertEqual(form["amount"].value(), "50.00")
        self.assertEqual(
            form["operation_key"].value(),
            operation_key,
        )

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(
            Payment.objects.get().amount,
            Decimal("40.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.fund_assignments.exists())
