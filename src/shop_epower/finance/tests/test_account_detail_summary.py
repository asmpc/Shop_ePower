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
from shop_epower.orders.services import assign_order_funds
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PayoutMethod,
)
from shop_epower.payments.services import (
    record_manual_account_payment,
    record_manual_account_payout,
)


class TestsManagerAccountSummaryViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

    # Карточка счёта клиента без заказов получает три нулевые суммы.
    # Чтение страницы не создаёт заказы или финансовые операции.
    def test_account_without_orders_has_zero_summary(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)

        account = response.context["account"]

        self.assertEqual(account.pk, self.account.pk)
        self.assertEqual(
            account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("0.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.user.orders.exists())
        self.assertFalse(self.account.transactions.exists())

    # До отгрузки из полученных 100 назначены заказу 60.
    # Сводка показывает свободные 40, предоплату 60 и долг 0.
    # Блок с понятными подписями расположен перед историей операций.
    # Чтение страницы не создаёт дополнительных финансовых операций.
    def test_summary_shows_assigned_prepayment_before_shipment(self):
        record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:summary:receipt",
            created_by=self.manager,
        )

        order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
            payment_method=PaymentMethod.ON_RECEIPT,
        )

        assign_order_funds(
            order=order,
            amount=Decimal("60.00"),
            operation_key="account:summary:assignment",
            created_by=self.manager,
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)

        account = response.context["account"]

        self.assertEqual(
            account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("60.00"),
        )
        self.assertEqual(
            account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertContains(response, "Financial summary")
        self.assertContains(response, "Available funds")
        self.assertContains(response, "Assigned prepayment")
        self.assertContains(response, "Shipped debt")

        self.assertLess(
            response.content.index(b"Financial summary"),
            response.content.index(b"Transactions"),
        )

    # Форма приёма денег находится на странице счёта и изначально свёрнута.
    # Кнопка раскрывает её под Payment actions вместо перехода на другую страницу.
    # Форма содержит ключ операции; чтение страницы не создаёт деньги или заказ.
    def test_account_detail_contains_collapsed_receipt_form(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            ),
        )

        receipt_url = reverse(
            "payments:manager_record_account_receipt",
            kwargs={"pk": self.account.pk},
        )
        panel_id = f"account-receipt-form-{self.account.pk}"

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register receipt")
        self.assertContains(
            response,
            f'data-bs-target="#{panel_id}"',
        )
        self.assertContains(
            response,
            f'<div class="collapse" id="{panel_id}">',
        )
        self.assertContains(
            response,
            f'action="{receipt_url}"',
        )
        self.assertNotContains(
            response,
            f'href="{receipt_url}?',
        )

        form = response.context["receipt_form"]
        operation_key = form.initial["operation_key"]

        self.assertTrue(operation_key)
        self.assertContains(
            response,
            f'value="{operation_key}"',
        )
        self.assertContains(
            response,
            'name="csrfmiddlewaretoken"',
        )

        self.assertLess(
            response.content.index(b"Financial summary"),
            response.content.index(b"Payment actions"),
        )
        self.assertLess(
            response.content.index(b"Payment actions"),
            response.content.index(b"Transactions"),
        )

        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(self.user.orders.exists())

    # Возврат из карточки сохраняет исходные параметры поиска и страницу.
    def test_account_back_link_preserves_search_context(self):
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

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            ),
            {"next": list_url},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], list_url)
        self.assertContains(
            response,
            f'href="{escape(list_url)}"',
        )

    # Переход из поиска в карточку и обратно сохраняет все параметры.
    # После возврата Account status остаётся выбранным в форме.
    def test_search_to_account_and_back_preserves_status_filter(self):
        parameters = {
            "q": self.user.email,
            "account_id": str(self.account.pk),
            "account_type": self.account.account_type,
            "status": self.account.status,
            "page": "1",
        }
        list_url = (
            reverse("finance:manager_account_list")
            + "?"
            + urlencode(parameters)
        )
        detail_url = (
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            )
            + "?"
            + urlencode({"next": list_url})
        )

        self.client.force_login(self.manager)

        list_response = self.client.get(list_url)

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(
            list_response,
            f'href="{escape(detail_url)}"',
        )

        detail_response = self.client.get(detail_url)

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.context["back_url"], list_url)

        returned_response = self.client.get(
            detail_response.context["back_url"],
        )

        self.assertEqual(returned_response.status_code, 200)
        self.assertEqual(
            returned_response.wsgi_request.GET.dict(),
            parameters,
        )
        self.assertContains(
            returned_response,
            (
                f'<option value="{self.account.status}" selected>'
                f'{self.account.get_status_display()}</option>'
            ),
            html=True,
        )

    # История транзакций изначально свёрнута.
    # Кнопка связана с раскрываемым блоком,
    # а существующая операция остаётся доступной для просмотра.
    def test_transaction_history_is_collapsed_by_default(self):
        operation_key = "account:collapsed-history:receipt"

        record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key=operation_key,
            created_by=self.manager,
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            """
            <button
                class="btn btn-outline-secondary btn-sm collapsed"
                type="button"
                data-bs-toggle="collapse"
                data-bs-target="#transaction-history"
                aria-expanded="false"
                aria-controls="transaction-history"
            >
                Transaction history
            </button>
            """,
            html=True,
        )
        self.assertContains(
            response,
            '<div class="collapse" id="transaction-history">',
        )
        self.assertContains(response, operation_key)

    # При переходе на другую страницу история остаётся раскрытой.
    # Кнопка также отражает раскрытое состояние блока.
    def test_transaction_history_stays_expanded_on_page_change(self):
        for index in range(21):
            record_manual_account_payment(
                account=self.account,
                amount=Decimal("1.00"),
                method=PaymentMethod.ON_RECEIPT,
                operation_key=f"account:expanded-history:{index}",
                created_by=self.manager,
            )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            ),
            {"transactions_page": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["transactions"].number,
            2,
        )
        self.assertEqual(len(response.context["transactions"]), 1)
        self.assertContains(
            response,
            '<div class="collapse show" id="transaction-history">',
        )
        self.assertContains(
            response,
            """
            <button
                class="btn btn-outline-secondary btn-sm"
                type="button"
                data-bs-toggle="collapse"
                data-bs-target="#transaction-history"
                aria-expanded="true"
                aria-controls="transaction-history"
            >
                Transaction history
            </button>
            """,
            html=True,
        )

    # Из счёта открывается список оплаченных ручных поступлений для отмены.
    # Payments содержит обратную ссылку в исходную карточку счёта.
    # Адрес возврата сохраняет параметры поиска и передаётся в форму фильтров.
    def test_receipt_cancellation_list_preserves_account_return_context(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("finance:manager_account_list")
            + "?"
            + urlencode(
                {
                    "q": self.user.email,
                    "account_type": self.account.account_type,
                    "status": self.account.status,
                    "page": 1,
                },
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
        payments_url = (
            reverse("payments:manager_payment_list")
            + "?"
            + urlencode(
                {
                    "account_id": self.account.pk,
                    "status": PaymentStatus.PAID,
                    "provider": PaymentProvider.MANUAL,
                    "next": account_url,
                },
            )
        )

        account_response = self.client.get(account_url)

        self.assertEqual(account_response.status_code, 200)
        self.assertContains(account_response, "Cancel receipt...")
        self.assertContains(
            account_response,
            f'href="{escape(payments_url)}"',
        )

        payments_response = self.client.get(payments_url)

        self.assertEqual(payments_response.status_code, 200)
        self.assertContains(payments_response, "Back to account")
        self.assertContains(
            payments_response,
            f'href="{escape(account_url)}"',
        )
        self.assertContains(
            payments_response,
            (
                '<input type="hidden" name="next" '
                f'value="{escape(account_url)}">'
            ),
            html=True,
        )

        returned_account = self.client.get(account_url)

        self.assertEqual(returned_account.status_code, 200)
        self.assertEqual(
            returned_account.context["back_url"],
            list_url,
        )

    # Форма возврата находится на странице счёта и изначально свёрнута.
    # Формы поступления и возврата имеют разные ключи операций и HTML ID.
    # Обе сохраняют адрес карточки с исходным поиском; деньги не изменяются.
    def test_account_detail_contains_collapsed_payout_form(self):
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
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                kwargs={"pk": self.account.pk},
            ),
            {"next": list_url},
        )

        payout_url = reverse(
            "payments:manager_record_account_payout",
            kwargs={"pk": self.account.pk},
        )
        panel_id = f"account-payout-form-{self.account.pk}"
        account_url = response.wsgi_request.get_full_path()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Return funds...")
        self.assertContains(
            response,
            f'data-bs-target="#{panel_id}"',
        )
        self.assertContains(
            response,
            f'<div class="collapse" id="{panel_id}">',
        )
        self.assertContains(
            response,
            f'action="{payout_url}"',
        )
        self.assertNotContains(
            response,
            f'href="{payout_url}?',
        )

        receipt_form = response.context["receipt_form"]
        payout_form = response.context["payout_form"]
        operation_key = payout_form.initial["operation_key"]

        self.assertTrue(operation_key)
        self.assertNotEqual(
            operation_key,
            receipt_form.initial["operation_key"],
        )
        self.assertNotEqual(
            payout_form["amount"].id_for_label,
            receipt_form["amount"].id_for_label,
        )
        self.assertContains(
            response,
            f'value="{operation_key}"',
        )
        self.assertContains(
            response,
            (
                '<input type="hidden" name="next" '
                f'value="{escape(account_url)}">'
            ),
            count=2,
            html=True,
        )

        self.assertFalse(self.account.transactions.exists())

    # Проверяем автора фактического возврата в истории счёта:
    # показывается сотрудник, подтвердивший выплату,
    # даже если карточку просматривает другой менеджер.
    def test_account_history_shows_payout_author(self):
        record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:summary:payout-author:receipt",
            created_by=self.manager,
            comment="Money received in the office.",
        )

        payout_author = create_test_manager()

        record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="account:summary:payout-author:payout",
            created_by=payout_author,
            comment="Money returned to the customer.",
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                kwargs={"pk": self.account.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Performed by:")
        self.assertContains(response, escape(payout_author.username))
