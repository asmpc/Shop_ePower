from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.payments.models import (
    Invoice,
    Payment,
    PaymentMethod,
    PaymentStatus,
)


class TestsManagerAccountReceiptViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

        self.url = reverse(
            "payments:manager_record_account_receipt",
            kwargs={"pk": self.account.pk},
        )

    # Менеджер открывает форму для счёта клиента без заказов.
    # Форма содержит поля поступления, CSRF и заранее созданный ключ.
    # Открытие страницы не создаёт денежные операции или заказ.
    def test_manager_can_open_account_receipt_form(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account"].pk, self.account.pk)
        self.assertContains(response, self.user.email)
        self.assertContains(response, 'name="amount"')
        self.assertContains(response, 'name="method"')
        self.assertContains(response, 'name="operation_key"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertTrue(
            response.context["form"].initial.get("operation_key"),
        )

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(self.user.orders.exists())

    # Менеджер подтверждает получение денег в офисе без заказа.
    # Создаются оплаченный Payment и одно пополнение.
    # После регистрации открывается карточка счёта.
    def test_manager_can_record_office_receipt_without_order(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        comment = "Advance received in the office."

        response = self.client.post(
            self.url,
            {
                "amount": "100.00",
                "method": PaymentMethod.ON_RECEIPT,
                "operation_key": operation_key,
                "comment": comment,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "finance:manager_account_detail",
                kwargs={"pk": self.account.pk},
            ),
        )

        payment = Payment.objects.get()
        deposit = self.account.transactions.get()

        self.assertIsNone(payment.order_id)
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.amount, Decimal("100.00"))
        self.assertEqual(payment.method, PaymentMethod.ON_RECEIPT)
        self.assertEqual(payment.manager_comment, comment)
        self.assertEqual(payment.deposit_transaction_id, deposit.pk)
        self.assertEqual(deposit.operation_key, operation_key)
        self.assertEqual(deposit.created_by_id, self.manager.pk)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.user.orders.exists())
        self.assertFalse(Invoice.objects.exists())

    # Переход в форму и обратно сохраняет адрес карточки
    # вместе с вложенным адресом исходного поиска.
    def test_account_to_receipt_and_back_preserves_search_context(self):
        list_url = (
            reverse("finance:manager_account_list")
            + "?"
            + urlencode(
                {
                    "q": self.user.email,
                    "account_id": self.account.pk,
                    "account_type": self.account.account_type,
                    "status": self.account.status,
                    "page": 1,
                }
            )
        )
        account_url = (
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            )
            + "?"
            + urlencode({"next": list_url})
        )
        form_url = self.url + "?" + urlencode({"next": account_url})

        self.client.force_login(self.manager)

        account_response = self.client.get(account_url)

        self.assertEqual(account_response.status_code, 200)
        self.assertContains(
            account_response,
            f'href="{escape(form_url)}"',
        )

        form_response = self.client.get(form_url)

        self.assertEqual(form_response.status_code, 200)
        self.assertEqual(
            form_response.context["return_url"],
            account_url,
        )
        self.assertContains(
            form_response,
            f'href="{escape(account_url)}"',
        )
        self.assertContains(
            form_response,
            (
                '<input type="hidden" name="next" '
                f'value="{escape(account_url)}">'
            ),
            html=True,
        )

        returned_response = self.client.get(
            form_response.context["return_url"],
        )

        self.assertEqual(returned_response.status_code, 200)
        self.assertEqual(
            returned_response.context["back_url"],
            list_url,
        )

    # После регистрации поступления менеджер возвращается
    # в карточку счёта с сохранённым адресом исходного поиска.
    def test_recording_receipt_preserves_search_context(self):
        list_url = (
            reverse("finance:manager_account_list")
            + "?"
            + urlencode(
                {
                    "q": self.user.email,
                    "account_id": self.account.pk,
                    "account_type": self.account.account_type,
                    "status": self.account.status,
                    "page": 1,
                }
            )
        )
        account_url = (
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            )
            + "?"
            + urlencode({"next": list_url})
        )

        self.client.force_login(self.manager)

        form_response = self.client.get(
            self.url,
            {"next": account_url},
        )
        self.assertEqual(form_response.status_code, 200)

        response = self.client.post(
            self.url,
            {
                "amount": "100.00",
                "method": PaymentMethod.ON_RECEIPT,
                "operation_key": (
                    form_response.context["form"]
                    .initial["operation_key"]
                ),
                "comment": "Advance received in the office.",
                "next": form_response.context["return_url"],
            },
            follow=True,
        )

        self.assertRedirects(response, account_url)
        self.assertEqual(
            response.context["back_url"],
            list_url,
        )

    # Сумма, превышающая размер поля Payment, отклоняется формой.
    # Введённые данные и ключ сохраняются, деньги не зачисляются.
    def test_too_large_amount_is_rejected_without_credit(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        amount = "10000000000.00"

        response = self.client.post(
            self.url,
            {
                "amount": amount,
                "method": PaymentMethod.ON_RECEIPT,
                "operation_key": operation_key,
                "comment": "Incorrect amount.",
            },
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertIn("amount", form.errors)
        self.assertEqual(form["amount"].value(), amount)
        self.assertEqual(
            form["operation_key"].value(),
            operation_key,
        )

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

    # Внешний адрес возврата заменяется карточкой текущего счёта.
    # Проверка действует при открытии формы и после поступления.
    def test_external_return_url_is_replaced_with_account_url(self):
        account_url = reverse(
            "finance:manager_account_detail",
            kwargs={"pk": self.account.pk},
        )
        external_url = "https://example.org/"

        self.client.force_login(self.manager)

        form_response = self.client.get(
            self.url,
            {"next": external_url},
        )

        self.assertEqual(form_response.status_code, 200)
        self.assertEqual(
            form_response.context["return_url"],
            account_url,
        )

        response = self.client.post(
            self.url,
            {
                "amount": "100.00",
                "method": PaymentMethod.ON_RECEIPT,
                "operation_key": (
                    form_response.context["form"]
                    .initial["operation_key"]
                ),
                "comment": "Advance received in the office.",
                "next": external_url,
            },
        )

        self.assertRedirects(response, account_url)

    # Повторная отправка одной формы не зачисляет деньги повторно.
    # Одинаковый ключ возвращает уже зарегистрированное поступление.
    def test_repeated_submission_does_not_credit_account_twice(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        receipt_data = {
            "amount": "100.00",
            "method": PaymentMethod.ON_RECEIPT,
            "operation_key": operation_key,
            "comment": "Advance received in the office.",
        }
        account_url = reverse(
            "finance:manager_account_detail",
            kwargs={"pk": self.account.pk},
        )

        first_response = self.client.post(self.url, receipt_data)
        repeated_response = self.client.post(self.url, receipt_data)

        self.assertRedirects(first_response, account_url)
        self.assertRedirects(repeated_response, account_url)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.account.transactions.count(), 1)

    # Клиент не может открыть служебную форму или внести деньги.
    # Прямой POST также запрещён и не создаёт финансовых операций.
    def test_customer_cannot_open_or_submit_receipt_form(self):
        self.client.force_login(self.user)

        form_response = self.client.get(self.url)

        self.assertEqual(form_response.status_code, 403)

        receipt_response = self.client.post(
            self.url,
            {
                "amount": "100.00",
                "method": PaymentMethod.ON_RECEIPT,
                "operation_key": "account-receipt:forbidden",
                "comment": "Attempt by customer.",
            },
        )

        self.assertEqual(receipt_response.status_code, 403)

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
