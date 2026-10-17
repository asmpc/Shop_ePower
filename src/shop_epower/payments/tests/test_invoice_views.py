from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.core.currency import get_base_currency
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import (
    DeliveryMethod,
    OrderStatus,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    Invoice,
    InvoiceStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import (
    cancel_invoice,
    create_invoice_for_order,
)
from shop_epower.payments.tests.helpers import (
    create_test_company_settings,
    create_test_invoice,
    create_test_payment,
)


class TestsInvoiceViews(TestCase):

    def setUp(self):
        self.client_user = create_test_user(
            email="client@test.com",
            username="client",
            password="testpass123",
        )

        self.manager = create_test_manager(
            email="manager@test.com",
            username="manager",
            password="testpass123",
        )

        self.admin = create_test_admin(
            email="admin@test.com",
            username="admin",
            password="testpass123",
        )

        self.order = create_test_order(
            user=self.client_user,
            status=OrderStatus.PROCESSING,
            payment_method=PaymentMethod.INVOICE,
            customer_name="Test Client",
            customer_email="client@test.com",
            customer_phone="+375291112233",
            delivery_method=DeliveryMethod.SHIPPING,
            delivery_provider="post",
            delivery_address="Minsk, Main street, 10",
            delivery_cost=Decimal("20.00"),
            total_price=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.MANUAL,
            amount=Decimal("100.00"),
            currency_snapshot=get_base_currency(),
        )

        self.company_settings = create_test_company_settings(
            company_name="Shop ePower LLC",
            short_company_name="Shop ePower",
            tax_id="123456789",
            tax_registration_reason_code="290101001",
            state_registration_number="1152901008622",
            legal_address="Seller legal address",
            actual_address="Seller actual address",
            bank_name="Seller Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
            bank_code="TESTBY22",
            correspondent_account="30101810100000000601",
            phone="+375291112233",
            email="seller@test.com",
        )

    def get_manager_order_list_url(self):
        return reverse(
            "orders:manager_order_list",
        )

    def get_expected_order_detail_url(self):
        manager_order_list_url = self.get_manager_order_list_url()

        manager_order_detail_url = reverse(
            "orders:manager_order_detail",
            args=[self.order.id],
        )

        return (
            f"{manager_order_detail_url}?"
            f"{urlencode({'next': manager_order_list_url})}"
        )

    # Проверяем manager workflow:
    # менеджер может создать invoice для оплаты по счету.
    def test_manager_can_generate_invoice(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "payments:manager_generate_invoice",
                args=[self.order.pk],
            ),
            data={
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

        self.assertEqual(
            Invoice.objects.count(),
            1,
        )

        invoice = Invoice.objects.first()

        self.assertEqual(invoice.order, self.order)
        self.assertIsNone(invoice.payment_id)
        self.assertEqual(invoice.amount, self.order.total_price)

    # Проверяем admin workflow:
    # администратор тоже может создать invoice.
    def test_admin_can_generate_invoice(self):
        self.client.force_login(
            self.admin,
        )

        response = self.client.post(
            reverse(
                "payments:manager_generate_invoice",
                args=[self.order.pk],
            ),
            data={
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

        self.assertEqual(
            Invoice.objects.count(),
            1,
        )

    # Проверяем права доступа:
    # клиент не может пользоваться manager endpoint
    # для создания invoice.
    def test_client_cannot_generate_invoice_from_manager_endpoint(self):
        self.client.force_login(
            self.client_user,
        )

        response = self.client.post(
            reverse(
                "payments:manager_generate_invoice",
                args=[self.order.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            Invoice.objects.count(),
            0,
        )

    # Пока у заказа есть действующий Invoice,
    # повторная выписка не создаёт второй документ.
    def test_cannot_generate_duplicate_invoice(self):
        self.client.force_login(
            self.manager,
        )

        generate_url = reverse(
            "payments:manager_generate_invoice",
            args=[self.order.pk],
        )

        request_data = {
            "next": self.get_manager_order_list_url(),
        }

        self.client.post(
            generate_url,
            data=request_data,
        )

        response = self.client.post(
            generate_url,
            data=request_data,
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

        self.assertEqual(
            Invoice.objects.count(),
            1,
        )

    # Менеджер может аннулировать Invoice, не связанный с Payment.
    # Причина, автор и время сохраняются; возврат ведёт в заказ.
    def test_manager_can_cancel_invoice_without_payment_link(self):
        invoice = create_invoice_for_order(
            order=self.order,
        )
        self.assertIsNone(invoice.payment_id)

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse(
                "payments:manager_cancel_invoice",
                args=[invoice.pk],
            ),
            data={
                "cancel_comment": "Wrong invoice data",
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.CANCELLED)
        self.assertEqual(invoice.cancel_comment, "Wrong invoice data")
        self.assertEqual(invoice.cancelled_by, self.manager)
        self.assertIsNotNone(invoice.cancelled_at)
        self.assertIsNone(invoice.payment_id)

    # Проверяем workflow:
    # администратор может отменить invoice.
    def test_admin_can_cancel_invoice(self):
        invoice = create_invoice_for_order(
            order=self.order,
        )

        self.client.force_login(
            self.admin,
        )

        response = self.client.post(
            reverse(
                "payments:manager_cancel_invoice",
                args=[invoice.id],
            ),
            data={
                "cancel_comment": "Wrong invoice data",
                "next": self.get_manager_order_list_url(),
            },
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.status,
            "cancelled",
        )

        self.assertEqual(
            invoice.cancel_comment,
            "Wrong invoice data",
        )

        self.assertEqual(
            invoice.cancelled_by,
            self.admin,
        )

        self.assertIsNotNone(
            invoice.cancelled_at,
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

    # Проверяем защиту:
    # повторная отмена invoice через endpoint
    # должна корректно обработать ValidationError.
    def test_cannot_cancel_invoice_twice(self):
        invoice = create_invoice_for_order(
            order=self.order,
        )

        self.client.force_login(
            self.admin,
        )

        cancel_url = reverse(
            "payments:manager_cancel_invoice",
            args=[invoice.id],
        )

        self.client.post(
            cancel_url,
            data={
                "cancel_comment": "First cancellation",
                "next": self.get_manager_order_list_url(),
            },
        )

        response = self.client.post(
            cancel_url,
            data={
                "cancel_comment": "Wrong invoice data",
                "next": self.get_manager_order_list_url(),
            },
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.cancel_comment,
            "First cancellation",
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

    # Менеджер выписывает Invoice для заказа до поступления денег.
    # Создание документа не создаёт Payment и не меняет балансы.
    def test_manager_can_generate_invoice_without_payment(self):
        account = create_personal_customer_account(
            user=self.client_user,
        )
        order = create_test_order(
            user=self.client_user,
            customer_account=account,
            status=OrderStatus.PROCESSING,
            payment_method=PaymentMethod.INVOICE,
            customer_phone="+375291112233",
        )

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse(
                "payments:manager_generate_invoice",
                args=[order.pk],
            ),
        )

        self.assertEqual(response.status_code, 302)

        invoice = Invoice.objects.get(order=order)
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertIsNone(invoice.payment_id)
        self.assertEqual(invoice.amount, order.total_price)
        self.assertFalse(order.payments.exists())

        account.refresh_from_db()
        self.assertEqual(account.available_balance, Decimal("0.00"))
        self.assertEqual(account.debt_balance, Decimal("0.00"))
        self.assertFalse(account.transactions.exists())

    # Для готового заказа без платежей отображается форма выписки Invoice.
    # Форма отправляет ID заказа, а не ID платежа.
    def test_ready_order_without_payments_shows_invoice_generation_form(self):
        account = create_personal_customer_account(
            user=self.client_user,
        )
        order = create_test_order(
            user=self.client_user,
            customer_account=account,
            status=OrderStatus.PROCESSING,
            payment_method=PaymentMethod.INVOICE,
            customer_phone="+375291112233",
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                args=[order.pk],
            ),
        )

        generate_url = reverse(
            "payments:manager_generate_invoice",
            args=[order.pk],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["invoice_workflow_state"],
            "ready",
        )
        self.assertContains(
            response,
            f'action="{generate_url}"',
        )
        self.assertFalse(order.payments.exists())

    # После аннулирования менеджер может выписать новый Invoice.
    # Старый документ сохраняет номер и сведения об отмене.
    def test_manager_can_reissue_invoice_after_cancellation(self):
        old_invoice = create_invoice_for_order(
            order=self.order,
        )
        old_number = old_invoice.invoice_number

        self.client.force_login(self.manager)
        request_data = {
            "next": self.get_manager_order_list_url(),
        }

        cancel_response = self.client.post(
            reverse(
                "payments:manager_cancel_invoice",
                args=[old_invoice.pk],
            ),
            data={
                **request_data,
                "cancel_comment": "Invoice requires correction.",
            },
        )

        self.assertRedirects(
            cancel_response,
            self.get_expected_order_detail_url(),
        )

        generate_response = self.client.post(
            reverse(
                "payments:manager_generate_invoice",
                args=[self.order.pk],
            ),
            data=request_data,
        )

        self.assertRedirects(
            generate_response,
            self.get_expected_order_detail_url(),
        )

        old_invoice.refresh_from_db()
        self.assertEqual(old_invoice.status, InvoiceStatus.CANCELLED)
        self.assertEqual(old_invoice.invoice_number, old_number)
        self.assertEqual(old_invoice.cancelled_by, self.manager)
        self.assertEqual(
            old_invoice.cancel_comment,
            "Invoice requires correction.",
        )

        current_invoice = Invoice.objects.get(
            order=self.order,
            status=InvoiceStatus.ISSUED,
        )

        self.assertNotEqual(current_invoice.pk, old_invoice.pk)
        self.assertNotEqual(current_invoice.invoice_number, old_number)
        self.assertIsNone(current_invoice.payment_id)
        self.assertEqual(
            Invoice.objects.filter(order=self.order).count(),
            2,
        )

    # Клиент не может аннулировать Invoice через служебный адрес.
    # Документ и сведения об отмене остаются без изменений.
    def test_client_cannot_cancel_invoice(self):
        invoice = create_invoice_for_order(
            order=self.order,
        )

        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse(
                "payments:manager_cancel_invoice",
                args=[invoice.pk],
            ),
            data={
                "cancel_comment": "Attempt to cancel invoice.",
            },
        )

        self.assertEqual(response.status_code, 403)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.cancel_comment, "")
        self.assertIsNone(invoice.cancelled_by)
        self.assertIsNone(invoice.cancelled_at)

    # Причина аннулирования обязательна и проверяется на сервере.
    # Даже прямой POST без комментария не должен отменять документ.
    def test_manager_cannot_cancel_invoice_without_comment(self):
        invoice = create_invoice_for_order(
            order=self.order,
        )

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse(
                "payments:manager_cancel_invoice",
                args=[invoice.pk],
            ),
            data={
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_order_detail_url(),
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.cancel_comment, "")
        self.assertIsNone(invoice.cancelled_by)
        self.assertIsNone(invoice.cancelled_at)

    # Карточка менеджера передаёт историю Invoice в шаблон.
    # История разбита на страницы по 20 документов.
    def test_manager_order_detail_contains_paginated_invoice_history(self):
        invoice = create_invoice_for_order(
            order=self.order,
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                args=[self.order.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)

        history = response.context["invoice_history"]
        self.assertEqual(list(history), [invoice])
        self.assertEqual(history.paginator.per_page, 20)

    # Из 21 документа первая страница содержит 20 новых,
    # а вторая — один самый старый Invoice.
    def test_manager_invoice_history_is_paginated(self):
        invoices = []

        for number in range(1, 22):
            invoice = create_test_invoice(
                order=self.order,
                payment=None,
                invoice_number=f"INV-2026-{number:06d}",
                status=InvoiceStatus.CANCELLED,
            )
            invoices.append(invoice)

        self.client.force_login(self.manager)
        detail_url = reverse(
            "orders:manager_order_detail",
            args=[self.order.pk],
        )

        first_response = self.client.get(detail_url)
        second_response = self.client.get(
            detail_url,
            {"invoices_page": 2},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        first_page = first_response.context["invoice_history"]
        second_page = second_response.context["invoice_history"]

        self.assertEqual(first_page.paginator.count, 21)
        self.assertEqual(first_page.paginator.num_pages, 2)
        self.assertEqual(
            list(first_page),
            list(reversed(invoices[1:])),
        )
        self.assertEqual(
            list(second_page),
            [invoices[0]],
        )

    # После перевыпуска история показывает старый Invoice,
    # причину аннулирования и ссылку на его PDF.
    def test_manager_order_detail_shows_cancelled_invoice_history(self):
        old_invoice = create_invoice_for_order(
            order=self.order,
        )
        cancel_invoice(
            invoice=old_invoice,
            cancelled_by=self.manager,
            comment="Incorrect company details.",
        )
        create_invoice_for_order(
            order=self.order,
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                args=[self.order.pk],
            ),
        )

        old_pdf_url = reverse(
            "payments:manager_invoice_pdf",
            args=[old_invoice.pk],
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invoice history")
        self.assertContains(response, old_invoice.invoice_number)
        self.assertContains(response, "Incorrect company details.")
        self.assertContains(
            response,
            f'href="{old_pdf_url}"',
        )

    # Ссылки истории переключают страницы и сохраняют next:
    # возврат к списку заказов не теряет фильтр и номер страницы.
    def test_invoice_history_pagination_preserves_list_context(self):
        for number in range(1, 22):
            create_test_invoice(
                order=self.order,
                payment=None,
                invoice_number=f"INV-2026-{number:06d}",
                status=InvoiceStatus.CANCELLED,
            )

        self.client.force_login(self.manager)
        detail_url = reverse(
            "orders:manager_order_detail",
            args=[self.order.pk],
        )
        list_url = (
            f"{self.get_manager_order_list_url()}"
            "?status=processing&page=2"
        )

        first_response = self.client.get(
            detail_url,
            {"next": list_url},
        )
        second_response = self.client.get(
            detail_url,
            {"next": list_url, "invoices_page": 2},
        )

        next_link = "?" + urlencode(
            {"next": list_url, "invoices_page": 2},
        )
        previous_link = "?" + urlencode(
            {"next": list_url, "invoices_page": 1},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(
            first_response,
            f'href="{escape(next_link)}"',
        )
        self.assertContains(
            second_response,
            f'href="{escape(previous_link)}"',
        )