from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.payments.models import PaymentMethod
from shop_epower.payments.services import record_manual_account_payment


class TestsAccountReceiptPaymentViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

    # Менеджер может открыть поступление клиента без заказа.
    # Карточка показывает email клиента и не предлагает открыть заказ.
    def test_manager_can_open_receipt_without_order(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:payment-detail",
            created_by=self.manager,
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                args=[payment.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["payment"], payment)
        self.assertContains(response, self.user.email)
        self.assertNotContains(response, "Open order")

    # Безналичное поступление без заказа не предполагает Invoice.
    # Карточка не сообщает об ожидании документа
    # и не предлагает скачать или аннулировать его.
    def test_bank_receipt_without_order_does_not_expect_invoice(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("60.00"),
            method=PaymentMethod.INVOICE,
            operation_key="account:receipt:bank-payment-detail",
            created_by=self.manager,
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                args=[payment.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            "Invoice has not been generated yet.",
        )
        self.assertNotContains(response, "Download invoice PDF")
        self.assertNotContains(response, "Cancel invoice")

    # Клиент не имеет доступа к служебной карточке платежа,
    # даже если поступление относится к его собственному счёту.
    def test_customer_cannot_open_staff_receipt_detail(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:staff-detail-forbidden",
            created_by=self.manager,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                args=[payment.pk],
            ),
        )

        self.assertEqual(response.status_code, 403)

    # Администратор может открыть поступление без заказа
    # и увидеть клиента, которому принадлежат деньги.
    def test_admin_can_open_receipt_without_order(self):
        admin = create_test_admin()

        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:admin-payment-detail",
            created_by=self.manager,
        )

        self.client.force_login(admin)

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                args=[payment.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.email)
        self.assertNotContains(response, "Open order")

    # Список показывает поступление без заказа:
    # клиента, ссылку на платёж и отсутствие ссылки на заказ.
    def test_staff_list_displays_receipt_without_order(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:staff-list",
            created_by=self.manager,
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("payments:manager_payment_list"),
            {
                "transaction_id": payment.transaction_id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["payments"]), [payment])
        self.assertContains(response, self.user.email)
        self.assertContains(response, "Open payment")
        self.assertNotContains(response, "Open order")

    # Страница передаёт email в селектор и показывает
    # только поступления выбранного клиента.
    # Введённый email сохраняется для формы поиска.
    def test_staff_email_search_returns_only_selected_customer_receipts(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(user=other_user)

        receipt_data = {
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "created_by": self.manager,
        }

        payment = record_manual_account_payment(
            account=self.account,
            operation_key="account:receipt:list-email:own",
            **receipt_data,
        )

        record_manual_account_payment(
            account=other_account,
            operation_key="account:receipt:list-email:other",
            **receipt_data,
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("payments:manager_payment_list"),
            {
                "customer_email": self.user.email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["payments"]), [payment])
        self.assertEqual(
            response.context["selected_customer_email"],
            self.user.email,
        )
        self.assertNotContains(response, other_user.email)
