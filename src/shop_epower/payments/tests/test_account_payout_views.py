from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import (
    AccountTransactionActorType,
    AccountTransactionType,
)
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


class TestsManagerAccountPayoutViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )

        record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:payout:view:deposit",
            created_by=self.manager,
            comment="Money received in the office.",
        )

        self.url = reverse(
            "payments:manager_record_account_payout",
            kwargs={"pk": self.account.pk},
        )

    # Проверяем открытие страницы выплаты менеджером:
    # отображается выбранный счёт и клиент,
    # просмотр не создаёт выплату и не изменяет деньги.
    def test_manager_can_open_account_payout_form(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["account"].pk,
            self.account.pk,
        )
        self.assertContains(response, self.user.email)

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

    # Проверяем состав формы выплаты:
    # доступны сумма, способ и причина;
    # форма содержит ключ защиты от повторов и CSRF-токен.
    def test_payout_form_contains_fields_and_operation_key(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="amount"')
        self.assertContains(response, 'name="method"')
        self.assertContains(response, 'name="comment"')
        self.assertContains(response, 'name="operation_key"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

        self.assertContains(response, 'value="cash"')
        self.assertContains(response, 'value="bank_transfer"')

        form = response.context["form"]

        self.assertTrue(form.initial.get("operation_key"))
        self.assertTrue(form.fields["comment"].required)

    # Проверяем подтверждение выплаты менеджером:
    # сохраняются выплата, источник, автор и причина,
    # свободный баланс уменьшается, долг не меняется.
    # После успешной отправки открывается карточка счёта.
    def test_manager_can_record_account_payout(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        comment = "Bank transfer returned to the customer."

        response = self.client.post(
            self.url,
            {
                "amount": "40.00",
                "method": PayoutMethod.BANK_TRANSFER,
                "comment": comment,
                "operation_key": operation_key,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "finance:manager_account_detail",
                kwargs={"pk": self.account.pk},
            ),
        )

        self.account.refresh_from_db()

        payout = CustomerPayout.objects.get()
        payout_transaction = payout.account_transaction

        self.assertEqual(payout.amount, Decimal("40.00"))
        self.assertEqual(payout.method, PayoutMethod.BANK_TRANSFER)
        self.assertEqual(
            payout_transaction.account_id,
            self.account.pk,
        )
        self.assertEqual(
            payout_transaction.operation_type,
            AccountTransactionType.PAYOUT,
        )
        self.assertEqual(payout_transaction.operation_key, operation_key)
        self.assertEqual(payout_transaction.created_by_id, self.manager.pk)
        self.assertEqual(payout_transaction.comment, comment)
        self.assertEqual(payout.sources.get().amount, Decimal("40.00"))

        self.assertEqual(
            self.account.available_balance,
            Decimal("60.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)

    # Проверяем обратную ссылку формы выплаты:
    # адрес карточки сохраняется вместе с вложенными
    # параметрами поиска счетов и номером страницы.
    def test_payout_form_back_link_preserves_account_search_context(self):
        list_url = (
            reverse("finance:manager_account_list")
            + "?"
            + urlencode(
                {
                    "q": self.user.email,
                    "account_id": self.account.pk,
                    "account_type": self.account.account_type,
                    "status": self.account.status,
                    "page": 2,
                }
            )
        )

        account_url = (
            reverse(
                "finance:manager_account_detail",
                kwargs={"pk": self.account.pk},
            )
            + "?"
            + urlencode({"next": list_url})
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            self.url,
            {"next": account_url},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["return_url"], account_url)
        self.assertContains(response, "Back to account")
        self.assertContains(
            response,
            f'href="{escape(account_url)}"',
        )
        self.assertContains(
            response,
            f'name="next" value="{escape(account_url)}"',
        )

    # Возврат подтверждается встроенной формой на странице счёта.
    # После отправки открывается карточка с обновлённым балансом.
    # Исходный фильтр и страница поиска счетов сохраняются.
    def test_successful_payout_preserves_account_return_context(self):
        list_url = (
            reverse("finance:manager_account_list")
            + "?status=active&page=2"
        )
        account_url = (
            reverse(
                "finance:manager_account_detail",
                kwargs={"pk": self.account.pk},
            )
            + "?"
            + urlencode({"next": list_url})
        )

        self.client.force_login(self.manager)

        form_response = self.client.get(account_url)

        self.assertEqual(form_response.status_code, 200)

        operation_key = (
            form_response.context["payout_form"]
            .initial["operation_key"]
        )

        response = self.client.post(
            self.url,
            {
                "amount": "40.00",
                "method": PayoutMethod.CASH,
                "comment": "Money returned to the customer.",
                "operation_key": operation_key,
                "next": form_response.context["return_url"],
            },
            follow=True,
        )

        self.assertRedirects(response, account_url)
        self.assertTemplateUsed(
            response,
            "finance/manage/account_detail.html",
        )
        self.assertEqual(response.context["back_url"], list_url)
        self.assertContains(
            response,
            f'href="{escape(list_url)}"',
        )
        self.assertEqual(
            response.context["account"].available_balance,
            Decimal("60.00"),
        )

    # При долге возврат отклоняется на странице счёта.
    # Форма возврата раскрыта, данные, ключ и контекст поиска сохранены.
    # Форма поступления свёрнута; деньги и история остаются без изменений.
    def test_payout_with_debt_preserves_form_data_and_shows_error(self):
        record_customer_debt(
            account=self.account,
            amount=Decimal("60.00"),
            operation_key="account:payout:view:shipment-debt",
            actor_type=AccountTransactionActorType.MANAGER,
            created_by=self.manager,
        )
        self.client.force_login(self.manager)

        list_url = (
            reverse("finance:manager_account_list")
            + "?"
            + urlencode(
                {
                    "q": self.user.email,
                    "status": self.account.status,
                },
            )
        )
        account_response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            ),
            {"next": list_url},
        )
        return_url = account_response.wsgi_request.get_full_path()
        operation_key = (
            account_response.context["payout_form"]
            .initial["operation_key"]
        )
        comment = "Customer requested a bank payout."

        response = self.client.post(
            self.url,
            {
                "amount": "40.00",
                "method": PayoutMethod.BANK_TRANSFER,
                "comment": comment,
                "operation_key": operation_key,
                "next": return_url,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "finance/manage/account_detail.html",
        )
        self.assertEqual(response.context["back_url"], list_url)
        self.assertContains(
            response,
            (
                '<div class="collapse show" '
                f'id="account-payout-form-{self.account.pk}">'
            ),
        )
        self.assertContains(
            response,
            (
                '<div class="collapse" '
                f'id="account-receipt-form-{self.account.pk}">'
            ),
        )

        form = response.context["payout_form"]
        error = "Customer account debt must be settled before payout."

        self.assertTrue(form.is_bound)
        self.assertFormError(form, None, error)
        self.assertContains(response, error)
        self.assertEqual(form["amount"].value(), "40.00")
        self.assertEqual(
            form["method"].value(),
            PayoutMethod.BANK_TRANSFER,
        )
        self.assertEqual(form["comment"].value(), comment)
        self.assertEqual(form["operation_key"].value(), operation_key)
        self.assertFalse(response.context["receipt_form"].is_bound)
        self.assertContains(
            response,
            (
                '<input type="hidden" name="next" '
                f'value="{escape(return_url)}">'
            ),
            html=True,
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

    # Проверяем запрет доступа клиента к выплатам:
    # просмотр формы и прямая отправка запроса возвращают 403,
    # даже если финансовый счёт принадлежит этому клиенту.
    def test_customer_cannot_open_or_submit_payout_form(self):
        self.client.force_login(self.user)

        get_response = self.client.get(self.url)

        self.assertEqual(get_response.status_code, 403)

        post_response = self.client.post(
            self.url,
            {
                "amount": "40.00",
                "method": PayoutMethod.CASH,
                "comment": "Customer attempts to confirm a payout.",
                "operation_key": "account:payout:view:forbidden-customer",
            },
        )

        self.assertEqual(post_response.status_code, 403)

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

    # Проверяем безопасный обратный переход:
    # внешний адрес отклоняется при открытии и отправке формы,
    # возврат происходит в карточку текущего счёта.
    def test_external_return_url_falls_back_to_current_account(self):
        unsafe_url = "https://example.org/"
        account_url = reverse(
            "finance:manager_account_detail",
            kwargs={"pk": self.account.pk},
        )

        self.client.force_login(self.manager)

        form_response = self.client.get(
            self.url,
            {"next": unsafe_url},
        )

        self.assertEqual(form_response.status_code, 200)
        self.assertEqual(
            form_response.context["return_url"],
            account_url,
        )

        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )

        response = self.client.post(
            self.url,
            {
                "amount": "40.00",
                "method": PayoutMethod.CASH,
                "comment": "Money returned to the customer.",
                "operation_key": operation_key,
                "next": unsafe_url,
            },
        )

        self.assertRedirects(response, account_url)
