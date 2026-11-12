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
)
from shop_epower.payments.services import record_manual_account_payment


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

    # Карточка счёта содержит ссылку на форму приёма денег.
    # Действия расположены после сводки и перед историей операций.
    def test_account_detail_links_to_receipt_form(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                args=[self.account.pk],
            ),
        )

        receipt_url = (
            reverse(
                "payments:manager_record_account_receipt",
                kwargs={"pk": self.account.pk},
            )
            + "?"
            + urlencode(
                {"next": response.wsgi_request.get_full_path()},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment actions")
        self.assertContains(response, "Register receipt")
        self.assertContains(
            response,
            f'href="{escape(receipt_url)}"',
        )

        self.assertLess(
            response.content.index(b"Financial summary"),
            response.content.index(b"Payment actions"),
        )
        self.assertLess(
            response.content.index(b"Payment actions"),
            response.content.index(b"Transactions"),
        )

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

    # Из карточки счёта можно выбрать поступление для отмены.
    # Ссылка ограничивает Payments счётом, статусом PAID
    # и ручным провайдером.
    def test_account_detail_links_to_paid_manual_receipts(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "finance:manager_account_detail",
                kwargs={"pk": self.account.pk},
            ),
        )

        payments_url = (
            reverse("payments:manager_payment_list")
            + "?"
            + urlencode(
                {
                    "account_id": self.account.pk,
                    "status": PaymentStatus.PAID,
                    "provider": PaymentProvider.MANUAL,
                }
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{escape(payments_url)}"',
        )
        self.assertContains(response, "Cancel receipt...")
