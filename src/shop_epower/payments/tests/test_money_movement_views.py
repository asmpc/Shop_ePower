from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.payments.models import PaymentMethod, PayoutMethod
from shop_epower.payments.services import (
    record_manual_account_payment,
    record_manual_account_payout,
)


class TestsManagerMoneyMovementViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )

        self.receipt = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="money-movement:view:receipt",
            created_by=self.manager,
            comment="Money received in the office.",
        )

        self.url = reverse("payments:manager_payment_list")

    # Проверяем отображение поступления и возврата в Payments:
    # возврат имеет пометку Returned и показывает своего автора,
    # даже если страницу просматривает другой менеджер.
    def test_list_shows_receipt_and_returned_payout_with_author(self):
        payout_author = create_test_manager()

        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="money-movement:view:payout",
            created_by=payout_author,
            comment="Money returned to the customer.",
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            self.url,
            {"account_id": self.account.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Payout #{payout.pk}")
        self.assertContains(response, "RETURNED")
        self.assertContains(response, f"Receipt #{self.receipt.pk}")
        self.assertContains(response, self.user.email)
        self.assertContains(response, "Performed by:")
        self.assertContains(response, escape(payout_author.username))

    # Проверяем поиск возвратов через статус:
    # выбранный Returned сохраняется, поступления исключаются,
    # отдельного переключателя вида движения в форме нет.
    def test_returned_filter_preserves_selection(self):
        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="money-movement:view:returned-filter",
            created_by=self.manager,
            comment="Money returned to the customer.",
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            self.url,
            {"status": "returned"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_status"], "returned")
        self.assertContains(
            response,
            '<option value="returned" selected>Returned</option>',
            html=True,
        )
        self.assertNotContains(response, 'name="kind"')
        self.assertContains(response, f"Payout #{payout.pk}")
        self.assertNotContains(
            response,
            f"Receipt #{self.receipt.pk}",
        )

    # Проверяем общую пагинацию поступлений и возвратов:
    # 21 движение распределяется между страницами как 20 и 1.
    # Новейшая выплата находится первой, старейшее поступление — на второй странице.
    def test_receipts_and_payouts_share_pagination(self):
        for number in range(19):
            record_manual_account_payment(
                account=self.account,
                amount=Decimal("100.00"),
                method=PaymentMethod.ON_RECEIPT,
                operation_key=f"money-movement:view:page-receipt:{number}",
                created_by=self.manager,
                comment="Additional receipt for pagination.",
            )

        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="money-movement:view:page-payout",
            created_by=self.manager,
            comment="Money returned to the customer.",
        )

        self.client.force_login(self.manager)

        first_page = self.client.get(
            self.url,
            {"account_id": self.account.pk},
        )
        second_page = self.client.get(
            self.url,
            {"account_id": self.account.pk, "page": 2},
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)

        first_entries = [
            (movement["kind"], movement["entry_id"])
            for movement in first_page.context["payments"]
        ]
        second_entries = [
            (movement["kind"], movement["entry_id"])
            for movement in second_page.context["payments"]
        ]

        self.assertEqual(first_page.context["paginator"].count, 21)
        self.assertEqual(len(first_entries), 20)
        self.assertEqual(len(second_entries), 1)
        self.assertEqual(first_entries[0], ("payout", payout.pk))
        self.assertEqual(
            second_entries,
            [("receipt", self.receipt.pk)],
        )
        self.assertContains(
            first_page,
            f'href="?account_id={self.account.pk}&amp;page=2"',
        )

    # Проверяем начальное открытие списка без условий поиска:
    # существующие Paid и Returned скрыты,
    # страница предлагает поиск вместо сообщения об отсутствии результатов.
    def test_initial_list_hides_existing_receipts_and_payouts(self):
        payout = record_manual_account_payout(
            account=self.account,
            amount=Decimal("40.00"),
            method=PayoutMethod.CASH,
            operation_key="money-movement:view:initial-list-payout",
            created_by=self.manager,
            comment="Money returned to the customer.",
        )

        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["payments"]), [])
        self.assertContains(
            response,
            "Payment history is hidden until you search or choose a filter.",
        )
        self.assertNotContains(response, "No payments found.")
        self.assertNotContains(
            response,
            f"Receipt #{self.receipt.pk}",
        )
        self.assertNotContains(response, f"Payout #{payout.pk}")
